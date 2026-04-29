import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from app.db import get_session
from app.models import Job, JobCreate, JobUpdate, JobStatus
from app.services import claude as claude_service
from app.services import pdf as pdf_service

router = APIRouter()


@router.get("/", response_model=List[Job])
def list_jobs(
    status: Optional[str] = None,
    session: Session = Depends(get_session)
):
    query = select(Job).order_by(Job.created_at.desc())
    if status:
        query = query.where(Job.status == status)
    return session.exec(query).all()


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/", response_model=Job)
def create_job(job_in: JobCreate, session: Session = Depends(get_session)):
    # Deduplicate by URL
    existing = session.exec(select(Job).where(Job.url == job_in.url)).first()
    if existing:
        return existing
    job = Job(**job_in.model_dump())
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.post("/bulk", response_model=List[Job])
def bulk_create_jobs(jobs_in: List[JobCreate], session: Session = Depends(get_session)):
    created = []
    for job_in in jobs_in:
        existing = session.exec(select(Job).where(Job.url == job_in.url)).first()
        if existing:
            created.append(existing)
            continue
        job = Job(**job_in.model_dump())
        session.add(job)
        session.commit()
        session.refresh(job)
        created.append(job)
    return created


@router.patch("/{job_id}", response_model=Job)
def update_job(job_id: int, update: JobUpdate, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(job, field, value)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.delete("/{job_id}")
def delete_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    session.delete(job)
    session.commit()
    return {"ok": True}


@router.post("/{job_id}/approve", response_model=Job)
def approve_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.approved
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.post("/{job_id}/skip", response_model=Job)
def skip_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.skipped
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.post("/{job_id}/tailor")
async def tailor_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.jd_text:
        raise HTTPException(status_code=400, detail="Job has no JD text")

    try:
        skill_md = claude_service.read_skill_md()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Tailor with Claude using SKILL.md as source of truth
    tailored = await claude_service.tailor_resume(skill_md, job.jd_text)
    job.tailored_data = json.dumps(tailored)

    # Generate PDF
    from app.api.resume import get_resume_settings
    settings = get_resume_settings(session)
    pdf_path = await pdf_service.generate_pdf(
        tailored,
        template=settings["template"],
        include_photo=settings["include_photo"],
        group_experience=settings.get("group_experience", False),
        job_id=job.id,
    )
    job.tailored_resume_path = str(pdf_path)

    session.add(job)
    session.commit()
    session.refresh(job)
    return {
        "job": job,
        "tailored": tailored,
        "skill_md": skill_md,
    }


@router.post("/{job_id}/tailor-cover-letter")
async def tailor_cover_letter(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.jd_text:
        raise HTTPException(status_code=400, detail="Job has no JD text")

    try:
        skill_md = claude_service.read_skill_md()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    cover_letter = await claude_service.generate_cover_letter(skill_md, job.jd_text, job.company)
    job.cover_letter = cover_letter
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"cover_letter": cover_letter}


@router.get("/{job_id}/tailored-data")
def get_tailored_data(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    tailored = json.loads(job.tailored_data) if job.tailored_data else None
    return {"tailored": tailored}


@router.get("/{job_id}/resume-pdf")
def get_resume_pdf(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.tailored_resume_path:
        raise HTTPException(status_code=404, detail="No PDF generated yet")
    path = Path(job.tailored_resume_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"PDF file not found at {path}")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )
