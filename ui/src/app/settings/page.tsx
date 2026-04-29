"use client"

import { useEffect, useState } from "react"
import { toast } from "sonner"
import { Save, Terminal, Loader2, CheckCircle, XCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"

interface Config {
  skill_md_path: string
  source_resume_path: string
  search: {
    keywords: string[]
    country: string
    city: string
    date_posted: string
    work_types: string[]
    max_applicants: number | null
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
  search: {
    keywords: [],
    country: "United States",
    city: "",
    date_posted: "past_week",
    work_types: ["remote"],
    max_applicants: null,
    blacklist_companies: [],
  },
  resume: {
    template: "modern",
    include_photo: false,
  },
}

const WORK_TYPES = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
]

const DATE_POSTED_OPTIONS = [
  { value: "past_day", label: "Past 24h" },
  { value: "past_week", label: "Past week" },
  { value: "past_month", label: "Past month" },
]

const APPLICANT_OPTIONS = [
  { value: null, label: "Any" },
  { value: 10, label: "< 10" },
  { value: 50, label: "< 50" },
  { value: 100, label: "< 100" },
]

export default function SettingsPage() {
  const [config, setConfig] = useState<Config>(DEFAULT_CONFIG)
  const [saving, setSaving] = useState(false)
  const [sessionStatus, setSessionStatus] = useState<boolean | null>(null)
  const [setupLoading, setSetupLoading] = useState(false)
  const [keywordsInput, setKeywordsInput] = useState("")
  const [blacklistInput, setBlacklistInput] = useState("")

  useEffect(() => {
    api.automation.sessionStatus()
      .then(d => setSessionStatus(d.has_session))
      .catch(() => setSessionStatus(false))

    const saved = localStorage.getItem("apply4me_config")
    if (saved) {
      const c = JSON.parse(saved)
      // Merge with defaults to handle old saved configs missing new fields
      const merged: Config = {
        ...DEFAULT_CONFIG,
        ...c,
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
      // Poll for session status
      setTimeout(async () => {
        const status = await api.automation.sessionStatus()
        setSessionStatus(status.has_session)
        setSetupLoading(false)
      }, 30_000)
    } catch {
      toast.error("Failed to open browser")
      setSetupLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      <div className="space-y-6">
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

        {/* LinkedIn Session */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">LinkedIn Session</CardTitle>
            <CardDescription>One-time setup to enable job scraping</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              {sessionStatus === null ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : sessionStatus ? (
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
              <Button variant="outline" size="sm" onClick={handleSetupSession} disabled={setupLoading}>
                {setupLoading ? (
                  <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                ) : (
                  <Terminal className="h-4 w-4 mr-1.5" />
                )}
                {sessionStatus ? "Re-authenticate" : "Set Up Session"}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              This opens a browser window where you log in to LinkedIn manually.
              Cookies are saved to ~/.apply4me/linkedin_cookies.json and reused for all scraping.
            </p>
          </CardContent>
        </Card>

        {/* Search Preferences */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Search Preferences</CardTitle>
            <CardDescription>Default settings for job scraping</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label>Job Keywords</Label>
              <Input
                value={keywordsInput}
                onChange={e => setKeywordsInput(e.target.value)}
                placeholder="QA Engineer, SDET, Test Engineer"
              />
              <p className="text-xs text-muted-foreground">Comma-separated. Used in LinkedIn search query.</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Country</Label>
                <Input
                  value={config.search.country}
                  onChange={e => setConfig(c => ({ ...c, search: { ...c.search, country: e.target.value } }))}
                  placeholder="United States"
                />
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
              <p className="text-xs text-muted-foreground">Only show jobs with fewer applicants than selected. "Any" disables the filter.</p>
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
          </CardContent>
        </Card>

        <Button onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Save className="h-4 w-4 mr-1.5" />}
          Save Settings
        </Button>
      </div>
    </div>
  )
}
