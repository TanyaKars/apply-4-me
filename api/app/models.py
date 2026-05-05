from datetime import datetime
from enum import Enum
from typing import Optional
import json
from sqlmodel import SQLModel, Field, Column, Text


class JobStatus(str, Enum):
    new = "new"
    approved = "approved"
    skipped = "skipped"
    applied = "applied"
    rejected = "rejected"
    pending = "pending"


class ATSType(str, Enum):
    greenhouse = "greenhouse"
    lever = "lever"
    ashby = "ashby"
    workday = "workday"
    unknown = "unknown"


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    company: str
    location: Optional[str] = None
    url: str = Field(unique=True)
    ats_url: Optional[str] = None
    jd_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    status: JobStatus = Field(default=JobStatus.new)
    ats_type: ATSType = Field(default=ATSType.unknown)
    tailored_resume_path: Optional[str] = None
    cover_letter: Optional[str] = Field(default=None, sa_column=Column(Text))
    applied_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tailored_data: Optional[str] = Field(default=None, sa_column=Column(Text))  # JSON
    match_score: Optional[int] = None
    match_reason: Optional[str] = Field(default=None, sa_column=Column(Text))


class ResumeConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="default")
    data: str = Field(sa_column=Column(Text))  # JSON blob
    template: str = Field(default="modern")
    include_photo: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AppConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True)
    value: str = Field(sa_column=Column(Text))


# Pydantic schemas (not DB tables)
class ResumeData(SQLModel):
    personal: dict = Field(default_factory=lambda: {
        "name": "", "email": "", "phone": "", "location": "",
        "linkedin": "", "github": "", "photo_path": ""
    })
    summary: str = ""
    experience: list = Field(default_factory=list)
    education: list = Field(default_factory=list)
    skills: list = Field(default_factory=list)
    certifications: list = Field(default_factory=list)


class JobCreate(SQLModel):
    title: str
    company: str
    location: Optional[str] = None
    url: str
    ats_url: Optional[str] = None
    jd_text: Optional[str] = None
    ats_type: ATSType = ATSType.unknown


class JobUpdate(SQLModel):
    status: Optional[JobStatus] = None
    ats_url: Optional[str] = None
    ats_type: Optional[ATSType] = None
