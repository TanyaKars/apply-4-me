"use client"

import { useEffect, useState } from "react"
import { toast } from "sonner"
import { Save, Terminal, Loader2, CheckCircle, XCircle, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"

interface Config {
  skill_md_path: string
  source_resume_path: string
  sources: string[]
  search: {
    keywords: string[]
    country: string
    city: string
    date_posted: string
    work_types: string[]
    max_applicants: number | null
    easy_apply_only: boolean
    blacklist_companies: string[]
  }
  resume: {
    template: string
    include_photo: boolean
  }
}

const DEFAULT_CONFIG: Config = {
  skill_md_path: "",
  source_resume_path: "",
  sources: ["linkedin"],
  search: {
    keywords: [],
    country: "United States",
    city: "",
    date_posted: "past_2hours",
    work_types: ["remote"],
    max_applicants: null,
    easy_apply_only: false,
    blacklist_companies: [],
  },
  resume: {
    template: "modern",
    include_photo: false,
  },
}

const ALL_SOURCES = [
  { value: "linkedin", label: "LinkedIn", available: true },
  { value: "builtin",  label: "Builtin",  available: true },
  { value: "indeed",   label: "Indeed",   available: false },
  { value: "jobright", label: "Jobright", available: false },
  { value: "wellfound",label: "Wellfound",available: false },
]

const WORK_TYPES = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
]

const DATE_POSTED_OPTIONS = [
  { value: "past_2hours", label: "Past 2h" },
]

const APPLICANT_OPTIONS = [
  { value: null, label: "Any" },
  { value: 10, label: "Early applicant (< 10)" },
]

function CollapsibleSection({
  title,
  badge,
  defaultOpen = false,
  children,
}: {
  title: string
  badge?: React.ReactNode
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <Card>
      <button
        type="button"
        className="w-full text-left"
        onClick={() => setOpen(o => !o)}
      >
        <CardHeader className="flex flex-row items-center justify-between py-4">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base">{title}</CardTitle>
            {badge}
          </div>
          <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", open && "rotate-180")} />
        </CardHeader>
      </button>
      {open && <CardContent className="pt-0 space-y-4">{children}</CardContent>}
    </Card>
  )
}

function ComingSoonContent({ name }: { name: string }) {
  return (
    <div className="py-6 text-center text-sm text-muted-foreground">
      {name} scraper coming soon
    </div>
  )
}

function BuiltinSessionSetup() {
  const [status, setStatus] = useState<{ has_session: boolean } | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.automation.builtin.sessionStatus()
      .then(setStatus)
      .catch(() => setStatus({ has_session: false }))
  }, [])

  async function handleSetup() {
    setLoading(true)
    try {
      const result = await api.automation.builtin.setupSession()
      toast.success(result.message ?? "Browser opened")
      const poll = async () => {
        const s = await api.automation.builtin.sessionStatus()
        setStatus(s)
        if (s.has_session) {
          setLoading(false)
        } else {
          setTimeout(poll, 3000)
        }
      }
      setTimeout(poll, 3000)
    } catch {
      toast.error("Failed to open browser")
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        {status === null ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : status.has_session ? (
          <div className="flex items-center gap-2 text-green-600">
            <CheckCircle className="h-4 w-4" />
            <span className="text-sm font-medium">Session active</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-orange-500">
            <XCircle className="h-4 w-4" />
            <span className="text-sm font-medium">No session</span>
          </div>
        )}
        <Button variant="outline" size="sm" onClick={handleSetup} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Terminal className="h-4 w-4 mr-1.5" />}
          {status?.has_session ? "Re-authenticate" : "Set Up Session"}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Opens a browser for manual login. Cookies saved to ~/.apply4me/builtin_cookies.json.
        Login is optional — Builtin job listings are publicly accessible without auth.
      </p>
      <p className="text-xs text-muted-foreground">
        Uses the same keywords and work type filters as the LinkedIn section.
      </p>
    </div>
  )
}

export default function SettingsPage() {
  const [config, setConfig] = useState<Config>(DEFAULT_CONFIG)
  const [saving, setSaving] = useState(false)
  const [sessionStatus, setSessionStatus] = useState<{ has_session: boolean; expired: boolean } | null>(null)
  const [setupLoading, setSetupLoading] = useState(false)
  const [keywordsInput, setKeywordsInput] = useState("")
  const [blacklistInput, setBlacklistInput] = useState("")
  const [locations, setLocations] = useState<{ name: string; geo_id: string }[]>([])

  useEffect(() => {
    api.automation.sessionStatus()
      .then(d => setSessionStatus(d))
      .catch(() => setSessionStatus({ has_session: false, expired: false }))

    api.automation.locations()
      .then(setLocations)
      .catch(() => {})

    const saved = localStorage.getItem("apply4me_config")
    if (saved) {
      const c = JSON.parse(saved)
      const merged: Config = {
        ...DEFAULT_CONFIG,
        ...c,
        sources: c.sources ?? DEFAULT_CONFIG.sources,
        search: { ...DEFAULT_CONFIG.search, ...c.search },
      }
      setConfig(merged)
      setKeywordsInput((merged.search?.keywords ?? []).join(", "))
      setBlacklistInput((merged.search?.blacklist_companies ?? []).join(", "))
    }
  }, [])

  function toggleWorkType(wt: string) {
    setConfig(c => {
      const current = c.search.work_types ?? []
      const next = current.includes(wt) ? current.filter(x => x !== wt) : [...current, wt]
      return { ...c, search: { ...c.search, work_types: next } }
    })
  }

  async function handleSave() {
    setSaving(true)
    const updated: Config = {
      ...config,
      search: {
        ...config.search,
        keywords: keywordsInput.split(",").map(s => s.trim()).filter(Boolean),
        blacklist_companies: blacklistInput.split(",").map(s => s.trim()).filter(Boolean),
      },
    }
    setConfig(updated)
    localStorage.setItem("apply4me_config", JSON.stringify(updated))

    await fetch("http://localhost:8000/api/automation/save-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updated),
    })

    toast.success("Settings saved")
    setSaving(false)
  }

  async function handleSetupSession() {
    setSetupLoading(true)
    try {
      const result = await api.automation.setupSession()
      toast.success(result.message ?? "Browser opened")
      const poll = async () => {
        const status = await api.automation.sessionStatus()
        setSessionStatus(status)
        if (status.has_session) {
          setSetupLoading(false)
        } else {
          setTimeout(poll, 3000)
        }
      }
      setTimeout(poll, 3000)
    } catch {
      toast.error("Failed to open browser")
      setSetupLoading(false)
    }
  }

  const sessionBadge = sessionStatus === null ? null : sessionStatus.has_session ? (
    <span className="flex items-center gap-1 text-xs text-green-600 font-normal">
      <CheckCircle className="h-3.5 w-3.5" /> Active
    </span>
  ) : sessionStatus.expired ? (
    <span className="flex items-center gap-1 text-xs text-red-500 font-normal">
      <XCircle className="h-3.5 w-3.5" /> Expired
    </span>
  ) : (
    <span className="flex items-center gap-1 text-xs text-orange-500 font-normal">
      <XCircle className="h-3.5 w-3.5" /> No session
    </span>
  )

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      <div className="space-y-4">
        {/* Resume Source */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Resume Files</CardTitle>
            <CardDescription>Paths to your resume source files on disk</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label>SKILL.md path</Label>
              <Input
                value={config.skill_md_path}
                onChange={e => setConfig(c => ({ ...c, skill_md_path: e.target.value }))}
                placeholder="apply4me/.claude/skills/resume/SKILL.md  (default)"
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Leave blank to use the default location. Edit this file in VS Code.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label>Source resume path (PDF or DOCX)</Label>
              <Input
                value={config.source_resume_path}
                onChange={e => setConfig(c => ({ ...c, source_resume_path: e.target.value }))}
                placeholder="/Users/you/resume.pdf"
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Used by "Parse → SKILL.md" on the Resume page.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Sources */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Sources</CardTitle>
            <CardDescription>Which job boards to scrape when clicking Scrape Jobs</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-1.5 flex-wrap">
              {ALL_SOURCES.map(src => {
                const active = (config.sources ?? []).includes(src.value)
                return (
                  <button
                    key={src.value}
                    type="button"
                    disabled={!src.available}
                    onClick={() => {
                      if (!src.available) return
                      setConfig(c => {
                        const current = c.sources ?? []
                        const next = current.includes(src.value)
                          ? current.filter(s => s !== src.value)
                          : [...current, src.value]
                        return { ...c, sources: next }
                      })
                    }}
                    className={cn(
                      "px-3 py-1.5 text-sm border rounded-md transition-colors",
                      !src.available && "opacity-40 cursor-not-allowed",
                      src.available && active && "bg-primary text-primary-foreground border-primary",
                      src.available && !active && "bg-background text-foreground border-input hover:bg-accent",
                    )}
                  >
                    {src.label}
                    {!src.available && <span className="ml-1.5 text-xs opacity-60">soon</span>}
                  </button>
                )
              })}
            </div>
          </CardContent>
        </Card>

        {/* LinkedIn */}
        <CollapsibleSection title="LinkedIn" badge={sessionBadge}>
          {/* Session */}
          <div className="space-y-3 pb-2 border-b">
            <div className="flex items-center gap-3">
              {sessionStatus === null ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : sessionStatus.has_session ? (
                <div className="flex items-center gap-2 text-green-600">
                  <CheckCircle className="h-4 w-4" />
                  <span className="text-sm font-medium">Session active</span>
                </div>
              ) : sessionStatus.expired ? (
                <div className="flex items-center gap-2 text-red-600">
                  <XCircle className="h-4 w-4" />
                  <span className="text-sm font-medium">Session expired — re-authenticate below</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-orange-500">
                  <XCircle className="h-4 w-4" />
                  <span className="text-sm font-medium">No session</span>
                </div>
              )}
              <Button variant="outline" size="sm" onClick={handleSetupSession} disabled={setupLoading}>
                {setupLoading ? (
                  <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                ) : (
                  <Terminal className="h-4 w-4 mr-1.5" />
                )}
                {sessionStatus?.has_session ? "Re-authenticate" : "Set Up Session"}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Opens a browser for manual login. Cookies saved to ~/.apply4me/linkedin_cookies.json.
            </p>
          </div>

          {/* Limitation note */}
          <div className="rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800">
            LinkedIn blocks pagination for scrapers, so only the first ~25 results are accessible. The "past 2h" window keeps those 25 slots as fresh as possible.
          </div>

          {/* Search filters */}
          <div className="space-y-1.5">
            <Label>Job Keywords</Label>
            <Input
              value={keywordsInput}
              onChange={e => setKeywordsInput(e.target.value)}
              placeholder="QA Engineer, SDET, Test Engineer"
            />
            <p className="text-xs text-muted-foreground">Comma-separated, max 5 positions.</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Country</Label>
              <select
                value={config.search.country}
                onChange={e => setConfig(c => ({ ...c, search: { ...c.search, country: e.target.value } }))}
                className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="">— select —</option>
                {locations.map(l => (
                  <option key={l.geo_id} value={l.name}>{l.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>City <span className="text-muted-foreground">(optional)</span></Label>
              <Input
                value={config.search.city}
                onChange={e => setConfig(c => ({ ...c, search: { ...c.search, city: e.target.value } }))}
                placeholder="San Francisco"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Work Type</Label>
            <div className="flex gap-1.5">
              {WORK_TYPES.map(wt => {
                const active = (config.search.work_types ?? []).includes(wt.value)
                return (
                  <button
                    key={wt.value}
                    type="button"
                    onClick={() => toggleWorkType(wt.value)}
                    className={cn(
                      "px-3 py-1.5 text-sm border rounded-md transition-colors",
                      active
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-background text-foreground border-input hover:bg-accent"
                    )}
                  >
                    {wt.label}
                  </button>
                )
              })}
            </div>
            <p className="text-xs text-muted-foreground">Select one or more. Leave none selected for any type.</p>
          </div>

          <div className="space-y-1.5">
            <Label>Date Posted</Label>
            <div className="flex gap-1.5">
              {DATE_POSTED_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setConfig(c => ({ ...c, search: { ...c.search, date_posted: opt.value } }))}
                  className={cn(
                    "px-3 py-1.5 text-sm border rounded-md transition-colors",
                    config.search.date_posted === opt.value
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background text-foreground border-input hover:bg-accent"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Max Applicants</Label>
            <div className="flex gap-1.5">
              {APPLICANT_OPTIONS.map(opt => (
                <button
                  key={String(opt.value)}
                  type="button"
                  onClick={() => setConfig(c => ({ ...c, search: { ...c.search, max_applicants: opt.value } }))}
                  className={cn(
                    "px-3 py-1.5 text-sm border rounded-md transition-colors",
                    config.search.max_applicants === opt.value
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background text-foreground border-input hover:bg-accent"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">Only show jobs with fewer applicants than selected.</p>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label>Easy Apply only</Label>
              <p className="text-xs text-muted-foreground mt-0.5">Only show jobs with LinkedIn Easy Apply</p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={config.search.easy_apply_only}
              onClick={() => setConfig(c => ({ ...c, search: { ...c.search, easy_apply_only: !c.search.easy_apply_only } }))}
              className={cn(
                "relative inline-flex h-6 w-11 shrink-0 rounded-full border-2 border-transparent transition-colors",
                config.search.easy_apply_only ? "bg-primary" : "bg-input"
              )}
            >
              <span className={cn(
                "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg transition-transform",
                config.search.easy_apply_only ? "translate-x-5" : "translate-x-0"
              )} />
            </button>
          </div>

          <div className="space-y-1.5">
            <Label>Company Blacklist</Label>
            <Input
              value={blacklistInput}
              onChange={e => setBlacklistInput(e.target.value)}
              placeholder="Company A, Company B"
            />
            <p className="text-xs text-muted-foreground">Comma-separated. Jobs from these companies are skipped.</p>
          </div>
        </CollapsibleSection>

        {/* Indeed */}
        <CollapsibleSection title="Indeed">
          <ComingSoonContent name="Indeed" />
        </CollapsibleSection>

        {/* Builtin */}
        <CollapsibleSection title="Builtin">
          <BuiltinSessionSetup />
        </CollapsibleSection>

        {/* Jobright */}
        <CollapsibleSection title="Jobright">
          <ComingSoonContent name="Jobright" />
        </CollapsibleSection>

        {/* Wellfound */}
        <CollapsibleSection title="Wellfound">
          <ComingSoonContent name="Wellfound" />
        </CollapsibleSection>

        <Button onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Save className="h-4 w-4 mr-1.5" />}
          Save Settings
        </Button>
      </div>
    </div>
  )
}
