import os
import json
from pathlib import Path
import anthropic


def get_api_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        return key
    config_file = Path.home() / ".apply4me" / "config.json"
    if config_file.exists():
        config = json.loads(config_file.read_text())
        return config.get("anthropic_api_key", "")
    raise ValueError("ANTHROPIC_API_KEY not set")


def get_skill_md_path() -> Path:
    config_file = Path.home() / ".apply4me" / "config.json"
    if config_file.exists():
        config = json.loads(config_file.read_text())
        custom = config.get("skill_md_path", "")
        if custom:
            return Path(custom).expanduser()
    # Default: .claude/skills/resume/SKILL.md in the project root
    return Path(__file__).parents[3] / ".claude" / "skills" / "resume" / "SKILL.md"


def read_skill_md() -> str:
    path = get_skill_md_path()
    if not path.exists():
        raise FileNotFoundError(
            f"SKILL.md not found at {path}. "
            "Set the path in Settings or create the file."
        )
    return path.read_text()


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text)


RESUME_JSON_SCHEMA = """{
  "personal": {
    "name": "...", "email": "...", "phone": "...", "location": "...",
    "linkedin": "...", "github": "...", "photo_path": "",
    "position": "exact job title from the JD"
  },
  "summary": "2-3 sentence professional summary",
  "experience": [
    {
      "title": "Job Title",
      "company": "Company Name",
      "dates": "Month Year – Month Year",
      "bullets": ["Achievement or responsibility", "..."]
    }
  ],
  "education": [{ "degree": "...", "school": "...", "year": "..." }],
  "skills": ["skill1", "skill2"],
  "certifications": [{ "name": "...", "issuer": "...", "year": "..." }]
}"""


async def tailor_resume(skill_md: str, jd_text: str) -> dict:
    """Generate a tailored resume JSON from SKILL.md + job description."""
    client = anthropic.Anthropic(api_key=get_api_key())

    prompt = f"""You are an expert resume writer. Tailor the candidate's resume for the job description below.

--- CANDIDATE BACKGROUND & PREFERENCES (SKILL.md) ---
{skill_md}

--- JOB DESCRIPTION ---
{jd_text}

Rules:
- Follow every preference stated in SKILL.md exactly — tone, bullet count, word choices, what to avoid, everything
- Do NOT fabricate experience, skills, or companies not mentioned in SKILL.md
- If the candidate held multiple roles at the same company, create a SEPARATE experience entry for each — never combine with "/" or "and"
- Extract the exact job title from the JD and put it in personal.position

Return ONLY valid JSON matching this schema, no explanation:
{RESUME_JSON_SCHEMA}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    return _parse_json_response(message.content[0].text)


async def generate_base_resume(skill_md: str) -> dict:
    """Generate a general (non-tailored) resume JSON from SKILL.md."""
    client = anthropic.Anthropic(api_key=get_api_key())

    prompt = f"""You are an expert resume writer. Convert the candidate's background below \
into a clean, professional resume.

--- CANDIDATE BACKGROUND & PREFERENCES (SKILL.md) ---
{skill_md}

Instructions:
- Follow all formatting preferences stated in the document
- Include all experience listed
- Present skills in the order given

Return ONLY valid JSON matching this schema, no explanation:
{RESUME_JSON_SCHEMA}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    return _parse_json_response(message.content[0].text)


async def parse_resume_to_skill_md(resume_text: str) -> str:
    """Convert extracted resume text into SKILL.md format."""
    client = anthropic.Anthropic(api_key=get_api_key())

    prompt = f"""Convert the resume below into a SKILL.md file.

SKILL.md is a personal background document with this structure:

```markdown
# Preferences
- Bullet points per role: 3-4
- [any other preferences you can infer from the resume style]

# Personal
Name: ...
Email: ...
Phone: ...
Location: ...
LinkedIn: ...
GitHub: ...

# Experience

## [Job Title] @ [Company] ([dates])
[Free-form description of the role, achievements, context, growth. Write naturally and include all details from the resume. More detail is better.]

# Education

## [Degree] @ [School] ([year])

# Skills
[comma-separated list]

# Certifications
## [Name] — [Issuer] ([year])
```

RESUME TEXT:
{resume_text}

Return only the SKILL.md content, no explanation."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text.strip()


async def generate_cover_letter(skill_md: str, jd_text: str, company: str) -> str:
    """Generate a cover letter from SKILL.md + job description."""
    client = anthropic.Anthropic(api_key=get_api_key())

    # Extract name from skill_md for personalization
    name = ""
    for line in skill_md.splitlines():
        if line.lower().startswith("name:"):
            name = line.split(":", 1)[1].strip()
            break

    prompt = f"""Write a compelling, concise cover letter for {name or "the candidate"} applying to {company}.

--- CANDIDATE BACKGROUND (SKILL.md) ---
{skill_md}

--- JOB DESCRIPTION ---
{jd_text}

Instructions:
- 3 paragraphs max
- Opening: hook specific to this company/role, no generic openers
- Middle: 2-3 achievements from their background that directly match the JD
- Closing: clear call to action
- Do NOT start with "I am writing to apply..."
- Do NOT use "I am passionate about" or similar clichés

Return only the cover letter text."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text.strip()
