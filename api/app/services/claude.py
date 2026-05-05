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


def read_ats_rules() -> str:
    path = Path(__file__).parents[3] / ".claude" / "skills" / "resume" / "ATS-RULES.md"
    if path.exists():
        return path.read_text()
    return ""


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
      "company": "Full Company Name exactly as in SKILL.md (e.g. 'PASV | United States (Part-time)')",
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
    ats_rules = read_ats_rules()

    ats_section = f"""
--- ATS OPTIMIZATION RULES (do not override) ---
{ats_rules}
""" if ats_rules else ""

    prompt = f"""You are an expert resume writer. Tailor the candidate's resume for the job description below.

--- CANDIDATE BACKGROUND & PREFERENCES (SKILL.md) ---
{skill_md}

--- JOB DESCRIPTION ---
{jd_text}
{ats_section}
Rules:
- Follow every preference stated in SKILL.md exactly — tone, bullet count, word choices, what to avoid, everything
- Do NOT fabricate experience, skills, or companies not mentioned in SKILL.md
- If the candidate held multiple roles at the same company, create a SEPARATE experience entry for each role — never combine with "/" or "and", never drop any role
- The "title" field must contain ONLY the job title (e.g. "QA Lead") — never embed dates in the title
- The "dates" field must contain ONLY the date range (e.g. "May 2019 – November 2021")
- The "company" field must contain the FULL company string exactly as written in SKILL.md, including location and type (e.g. "PASV | United States (Part-time)")
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
- If the candidate held multiple roles at the same company, create a SEPARATE experience entry for each role — never combine with "/" or "and", never drop any role
- The "title" field must contain ONLY the job title (e.g. "QA Lead") — never embed dates in the title
- The "dates" field must contain ONLY the date range (e.g. "May 2019 – November 2021")
- The "company" field must contain the FULL company string exactly as written in SKILL.md, including location and type (e.g. "PASV | United States (Part-time)")

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


async def score_job(skill_md: str, jd_text: str, title: str) -> dict:
    """Return {"score": 0-100, "reason": str} for how well the candidate matches the job."""
    client = anthropic.Anthropic(api_key=get_api_key())
    prompt = f"""Score how well this candidate matches the job on a scale of 0-100.

--- CANDIDATE BACKGROUND (SKILL.md) ---
{skill_md[:3000]}

--- JOB ---
Title: {title}
{jd_text[:2000]}

Scoring guide:
- 80-100: Strong match — most required skills/experience align
- 50-79:  Partial match — some key requirements met
- 0-49:   Weak match — significant skill or experience gaps

Return ONLY valid JSON, no explanation:
{{"score": <integer 0-100>, "reason": "<one sentence, max 100 chars>"}}"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=128,
        messages=[{"role": "user", "content": prompt}]
    )
    return _parse_json_response(message.content[0].text)


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
