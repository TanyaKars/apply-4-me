import json
from pathlib import Path
from typing import Optional
import jinja2
from weasyprint import HTML, CSS

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
OUTPUT_DIR = Path.home() / ".appy4me" / "resumes"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def generate_pdf(
    resume_data: dict,
    template: str = "modern",
    include_photo: bool = False,
    job_id: Optional[int] = None
) -> Path:
    """Render Jinja2 template -> WeasyPrint -> PDF."""

    template_dir = TEMPLATES_DIR / template
    loader = jinja2.FileSystemLoader(str(template_dir))
    env = jinja2.Environment(loader=loader)

    tmpl = env.get_template("resume.html")

    # Handle photo
    photo_data_uri = None
    if include_photo:
        photo_path_str = resume_data.get("personal", {}).get("photo_path", "")
        if photo_path_str:
            photo_path = Path(photo_path_str)
            if photo_path.exists():
                import base64
                suffix = photo_path.suffix.lower()
                mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
                b64 = base64.b64encode(photo_path.read_bytes()).decode()
                photo_data_uri = f"data:{mime};base64,{b64}"

    html_content = tmpl.render(
        resume=resume_data,
        include_photo=include_photo,
        photo_data_uri=photo_data_uri
    )

    filename = f"job_{job_id}.pdf" if job_id else "resume.pdf"
    output_path = OUTPUT_DIR / filename

    HTML(string=html_content, base_url=str(template_dir)).write_pdf(str(output_path))

    return output_path
