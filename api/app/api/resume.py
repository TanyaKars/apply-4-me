import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlmodel import Session, select
from app.db import get_session
from app.models import ResumeConfig, ResumeData
from app.services import pdf as pdf_service
from app.services import claude as claude_service
from app.services import parser as parser_service

router = APIRouter()

TEMPLATES = ["modern", "classic", "minimal"]


def get_resume_settings(session: Session) -> dict:
    """Return template + photo settings (not resume data)."""
    config = session.exec(select(ResumeConfig).where(ResumeConfig.name == "default")).first()
    if not config:
        return {"template": "modern", "include_photo": False, "photo_path": ""}
    data = json.loads(config.data) if config.data else {}
    return {
        "template": config.template,
        "include_photo": config.include_photo,
        "photo_path": data.get("personal", {}).get("photo_path", ""),
    }


@router.get("/settings")
def get_settings(session: Session = Depends(get_session)):
    return get_resume_settings(session)


@router.put("/settings")
def save_settings(payload: dict, session: Session = Depends(get_session)):
    config = session.exec(select(ResumeConfig).where(ResumeConfig.name == "default")).first()
    if not config:
        config = ResumeConfig(
            name="default",
            data=json.dumps({"personal": {"photo_path": payload.get("photo_path", "")}}),
            template=payload.get("template", "modern"),
            include_photo=payload.get("include_photo", False),
        )
    else:
        config.template = payload.get("template", config.template)
        config.include_photo = payload.get("include_photo", config.include_photo)
        existing = json.loads(config.data) if config.data else {}
        existing.setdefault("personal", {})["photo_path"] = payload.get("photo_path", "")
        config.data = json.dumps(existing)
    session.add(config)
    session.commit()
    return {"ok": True}


@router.get("/skill-md")
def get_skill_md():
    path = claude_service.get_skill_md_path()
    if not path.exists():
        return {"content": "", "path": str(path), "exists": False}
    return {"content": path.read_text(), "path": str(path), "exists": True}


@router.get("/templates")
def list_templates():
    return {"templates": TEMPLATES}


class ParseSourceRequest(BaseModel):
    source_path: str


@router.post("/parse-source")
async def parse_source(req: ParseSourceRequest):
    """Extract text from PDF/DOCX at given path and convert to SKILL.md via Claude."""
    try:
        raw_text = parser_service.extract_text(req.source_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    skill_md_content = await claude_service.parse_resume_to_skill_md(raw_text)

    # Write to configured SKILL.md path
    skill_md_path = claude_service.get_skill_md_path()
    skill_md_path.parent.mkdir(parents=True, exist_ok=True)
    skill_md_path.write_text(skill_md_content)

    return {"content": skill_md_content, "path": str(skill_md_path)}


@router.post("/generate-pdf")
async def generate_pdf(session: Session = Depends(get_session)):
    """Generate a base (non-tailored) PDF from SKILL.md."""
    try:
        skill_md = claude_service.read_skill_md()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    resume_data = await claude_service.generate_base_resume(skill_md)

    settings = get_resume_settings(session)
    pdf_path = await pdf_service.generate_pdf(
        resume_data,
        template=settings["template"],
        include_photo=settings["include_photo"],
    )
    return {"pdf_path": str(pdf_path)}


@router.post("/upload-photo")
async def upload_photo(file: UploadFile = File(...)):
    photos_dir = Path.home() / ".apply4me" / "photos"
    photos_dir.mkdir(exist_ok=True)
    photo_path = photos_dir / file.filename
    content = await file.read()
    photo_path.write_bytes(content)
    return {"photo_path": str(photo_path)}


# Keep for backward compat (tailored data diff still uses this shape)
def get_active_resume(session: Session) -> dict:
    config = session.exec(select(ResumeConfig).where(ResumeConfig.name == "default")).first()
    if not config or not config.data:
        return ResumeData().model_dump()
    return json.loads(config.data)
