const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export type JobStatus = "new" | "approved" | "skipped" | "applied" | "rejected"
export type ATSType = "greenhouse" | "lever" | "ashby" | "workday" | "icims" | "taleo" | "smartrecruiters" | "jobvite" | "brassring" | "successfactors" | "easy_apply" | "external" | "unknown"

export interface Job {
  id: number
  title: string
  company: string
  location: string | null
  url: string
  ats_url: string | null
  jd_text: string | null
  status: JobStatus
  ats_type: ATSType
  tailored_resume_path: string | null
  cover_letter: string | null
  applied_at: string | null
  created_at: string
  tailored_data: string | null
}

export interface ResumePersonal {
  name: string
  email: string
  phone: string
  location: string
  linkedin: string
  github: string
  photo_path: string
}

export interface ResumeExperience {
  title: string
  company: string
  dates: string
  bullets: string[]
}

export interface ResumeEducation {
  degree: string
  school: string
  year: string
}

export interface ResumeCertification {
  name: string
  issuer: string
  year: string
}

export interface ResumeData {
  personal: ResumePersonal
  summary: string
  experience: ResumeExperience[]
  education: ResumeEducation[]
  skills: string[]
  certifications: ResumeCertification[]
}

export interface ResumePayload {
  data: ResumeData
  template: string
  include_photo: boolean
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`API error ${res.status}: ${err}`)
  }
  return res.json() as Promise<T>
}

// Jobs
export const api = {
  jobs: {
    list: (status?: string) =>
      request<Job[]>(`/api/jobs/${status ? `?status=${status}` : ""}`),
    get: (id: number) => request<Job>(`/api/jobs/${id}`),
    approve: (id: number) => request<Job>(`/api/jobs/${id}/approve`, { method: "POST" }),
    skip: (id: number) => request<Job>(`/api/jobs/${id}/skip`, { method: "POST" }),
    unskip: (id: number) => request<Job>(`/api/jobs/${id}/unskip`, { method: "POST" }),
    markApplied: (id: number) => request<Job>(`/api/jobs/${id}/mark-applied`, { method: "POST" }),
    tailor: (id: number) => request<{ job: Job; tailored: ResumeData; skill_md: string }>(
      `/api/jobs/${id}/tailor`, { method: "POST" }
    ),
    tailorCoverLetter: (id: number) =>
      request<{ cover_letter: string }>(`/api/jobs/${id}/tailor-cover-letter`, { method: "POST" }),
    getTailoredData: (id: number) =>
      request<{ tailored: ResumeData | null }>(`/api/jobs/${id}/tailored-data`),
    delete: (id: number) => request<{ ok: boolean }>(`/api/jobs/${id}`, { method: "DELETE" }),
    clearNew: () => request<{ deleted: number }>("/api/jobs/clear-new", { method: "DELETE" }),
  },
  resume: {
    settings: () => request<{ template: string; include_photo: boolean; photo_path: string; group_experience: boolean }>("/api/resume/settings"),
    saveSettings: (s: { template: string; include_photo: boolean; photo_path: string; group_experience: boolean }) =>
      request<{ ok: boolean }>("/api/resume/settings", { method: "PUT", body: JSON.stringify(s) }),
    skillMd: () => request<{ content: string; path: string; exists: boolean }>("/api/resume/skill-md"),
    parseSource: (source_path: string) =>
      request<{ content: string; path: string }>("/api/resume/parse-source", {
        method: "POST",
        body: JSON.stringify({ source_path }),
      }),
    generatePdf: () => request<{ pdf_path: string }>("/api/resume/generate-pdf", { method: "POST" }),
    templates: () => request<{ templates: string[] }>("/api/resume/templates"),
  },
  automation: {
    locations: () => request<{ name: string; geo_id: string }[]>("/api/automation/locations"),
    sessionStatus: () => request<{ has_session: boolean; expired: boolean; expires_at: number | null }>("/api/automation/session-status"),
    setupSession: () => request<{ status: string; message: string }>("/api/automation/setup-session", { method: "POST" }),
    scrapeStatus: () => request<{ running: boolean; pid?: number }>("/api/automation/scrape-status"),
    scrape: (config: {
      keywords: string[]
      location?: string
      country?: string
      city?: string
      date_posted?: string
      work_types?: string[]
      max_applicants?: number | null
      easy_apply_only?: boolean
    }) =>
      request<{ status: string }>("/api/automation/scrape", {
        method: "POST",
        body: JSON.stringify(config),
      }),
    apply: (jobId: number) =>
      request<{ status: string }>(`/api/automation/apply/${jobId}`, { method: "POST" }),
    builtin: {
      sessionStatus: () =>
        request<{ has_session: boolean }>("/api/automation/builtin/session-status"),
      setupSession: () =>
        request<{ status: string; message: string }>("/api/automation/builtin/setup-session", { method: "POST" }),
      scrape: (config: { keywords: string[]; work_types?: string[] }) =>
        request<{ status: string }>("/api/automation/builtin/scrape", {
          method: "POST",
          body: JSON.stringify(config),
        }),
      scrapeStatus: () =>
        request<{ running: boolean; pid?: number }>("/api/automation/builtin/scrape-status"),
    },
  },
  health: () => request<{ status: string }>("/api/health"),
}
