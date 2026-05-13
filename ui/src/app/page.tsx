"use client"

import { useEffect, useState, useCallback, ReactNode } from "react"
import { toast } from "sonner"
import { Link, RefreshCw, Search, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { JobCard } from "@/components/job-card"
import { api, type Job } from "@/lib/api"

// ── Session chip helpers ──────────────────────────────────────────────────────

type ChipColor = "green" | "yellow" | "red"

function chipColor(hasSession: boolean, expiresAt: number | null): ChipColor {
  if (!hasSession) return "red"
  if (expiresAt === null) return "green"           // no tracked expiry (Builtin)
  const mins = (expiresAt - Date.now() / 1000) / 60
  if (mins >= 15) return "green"
  if (mins >= 5)  return "yellow"
  return "red"
}

function chipTooltip(label: string, hasSession: boolean, expiresAt: number | null): string {
  if (!hasSession) return `${label} · No session — go to Settings`
  if (expiresAt === null) return `${label} · Session active`
  const secs = Math.max(0, expiresAt - Date.now() / 1000)
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const timeStr = h > 0 ? `${h}h ${m}m` : `${m}m`
  return `${label} · ${timeStr} remaining`
}

function LinkedInIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
      <circle cx="2.5" cy="2.5" r="1.5" />
      <rect x="1.5" y="5" width="2" height="9" rx="0.4" />
      <rect x="5.5" y="5" width="2" height="9" rx="0.4" />
      <path d="M7.5 8.2C8 6.4 9.3 5 11 5c2 0 3.5 1.3 3.5 3.8V14h-2V9.2c0-1.2-.6-2-1.8-2s-2 .8-2 2V14h-2V8.2z" />
    </svg>
  )
}

function BuiltinIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
      <path d="M1 15V6.8L8 2l7 4.8V15H1zm2-2h3V8H3v5zm4 0h3V8H7v5zm4 0h2V8h-2v5z" />
    </svg>
  )
}

function SessionChip({ label, icon, hasSession, expiresAt }: {
  label: string
  icon: ReactNode
  hasSession: boolean
  expiresAt: number | null
}) {
  const color = chipColor(hasSession, expiresAt)
  const tooltip = chipTooltip(label, hasSession, expiresAt)
  return (
    <div
      title={tooltip}
      className={cn(
        "w-7 h-7 rounded-md border-2 flex items-center justify-center cursor-default shrink-0 transition-colors",
        color === "green"  && "border-green-500  bg-green-50  text-green-700",
        color === "yellow" && "border-yellow-400 bg-yellow-50 text-yellow-700",
        color === "red"    && "border-red-400    bg-red-50    text-red-600",
      )}
    >
      {icon}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [scrapingSource, setScrapingSource] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState("all")
  const [matchFilter, setMatchFilter] = useState("all")
  const [search, setSearch] = useState("")
  const [linkedinSession, setLinkedinSession] = useState<{ has_session: boolean; expires_at: number | null } | null>(null)
  const [builtinSession, setBuiltinSession]   = useState<{ has_session: boolean } | null>(null)
  const [clearing, setClearing] = useState(false)
  const [urlInput, setUrlInput] = useState("")
  const [pastedJd, setPastedJd] = useState("")
  const [addingUrl, setAddingUrl] = useState(false)

  const loadJobs = useCallback(async () => {
    try {
      const data = await api.jobs.list()
      setJobs(data)
    } catch {
      toast.error("Failed to load jobs")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadJobs() }, [loadJobs])

  useEffect(() => {
    api.automation.sessionStatus()
      .then(s => setLinkedinSession({ has_session: s.has_session, expires_at: s.expires_at }))
      .catch(() => setLinkedinSession({ has_session: false, expires_at: null }))

    api.automation.builtin.sessionStatus()
      .then(s => setBuiltinSession({ has_session: s.has_session }))
      .catch(() => setBuiltinSession({ has_session: false }))
  }, [])

  function pollUntilDone(statusFn: () => Promise<{ running: boolean }>) {
    return new Promise<void>(resolve => {
      const check = async () => {
        try {
          const s = await statusFn()
          s.running ? setTimeout(check, 5000) : resolve()
        } catch {
          resolve()
        }
      }
      setTimeout(check, 5000)
    })
  }

  async function handleScrapeAll() {
    const saved = localStorage.getItem("apply4me_config")
    const cfg = saved ? JSON.parse(saved) : {}
    const sources: string[] = cfg.sources ?? ["linkedin"]
    const s = cfg.search ?? {}
    const keywords = s.keywords?.length ? s.keywords : ["QA Engineer", "SDET"]
    const workTypes: string[] = s.work_types ?? []

    if (sources.includes("linkedin")) {
      if (!linkedinSession?.has_session) {
        toast.error("LinkedIn session missing — go to Settings to re-authenticate.")
      } else {
        try {
          setScrapingSource("linkedin")
          await api.automation.scrape({
            keywords,
            country: s.country ?? "",
            city: s.city ?? "",
            date_posted: s.date_posted ?? "past_2hours",
            work_types: workTypes,
            max_applicants: s.max_applicants ?? null,
            easy_apply_only: s.easy_apply_only ?? false,
          })
          await pollUntilDone(api.automation.scrapeStatus)
          toast.success("LinkedIn scrape finished")
        } catch {
          toast.error("Failed to start LinkedIn scrape")
        }
      }
    }

    if (sources.includes("builtin")) {
      try {
        setScrapingSource("builtin")
        const b = cfg.builtin ?? {}
        const builtinKeywords = b.keywords?.length ? b.keywords : keywords
        await api.automation.builtin.scrape({
          keywords: builtinKeywords,
          work_types: b.work_types ?? workTypes,
          days_since_updated: b.days_since_updated ?? null,
          country: b.country ?? "United States",
          state: b.state ?? "",
        })
        await pollUntilDone(api.automation.builtin.scrapeStatus)
        toast.success("Builtin scrape finished")
      } catch {
        toast.error("Failed to start Builtin scrape")
      }
    }

    setScrapingSource(null)
    await loadJobs()
  }

  async function handleClearNew() {
    if (!confirm(`Delete all ${counts.new} new jobs? Approved, applied, and skipped jobs will be kept.`)) return
    setClearing(true)
    try {
      const result = await api.jobs.clearNew()
      toast.success(`Cleared ${result.deleted} new jobs`)
      loadJobs()
    } catch {
      toast.error("Failed to clear jobs")
    } finally {
      setClearing(false)
    }
  }

  async function handleAddFromUrl() {
    const url = urlInput.trim()
    if (!url) return
    setAddingUrl(true)
    try {
      const job = await api.jobs.fromUrl(url, pastedJd.trim() || undefined)
      setJobs(prev => {
        if (prev.some(j => j.id === job.id)) return prev
        return [job, ...prev]
      })
      setUrlInput("")
      setPastedJd("")
      toast.success(`Added: ${job.title} @ ${job.company}`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to add job")
    } finally {
      setAddingUrl(false)
    }
  }

  function handleJobUpdate(updated: Job) {
    setJobs(prev => prev.map(j => j.id === updated.id ? updated : j))
  }

  function matchBucket(score: number | null | undefined) {
    if (score === null || score === undefined) return "unscored"
    if (score >= 80) return "excellent"
    if (score >= 60) return "good"
    if (score >= 40) return "fair"
    return "low"
  }

  const statusFiltered = jobs.filter(j => {
    if (statusFilter === "all" && j.status === "skipped") return false
    if (statusFilter !== "all" && j.status !== statusFilter) return false
    return true
  })

  const filtered = statusFiltered.filter(j => {
    if (matchFilter !== "all" && matchBucket(j.match_score) !== matchFilter) return false
    if (search) {
      const q = search.toLowerCase()
      if (
        !j.title.toLowerCase().includes(q) &&
        !j.company.toLowerCase().includes(q) &&
        !(j.location ?? "").toLowerCase().includes(q)
      ) return false
    }
    return true
  })

  const counts = {
    new:      jobs.filter(j => j.status === "new").length,
    approved: jobs.filter(j => j.status === "approved").length,
    applied:  jobs.filter(j => j.status === "applied").length,
    skipped:  jobs.filter(j => j.status === "skipped").length,
    pending:  jobs.filter(j => j.status === "pending").length,
  }

  const matchCounts = {
    excellent: statusFiltered.filter(j => matchBucket(j.match_score) === "excellent").length,
    good:      statusFiltered.filter(j => matchBucket(j.match_score) === "good").length,
    fair:      statusFiltered.filter(j => matchBucket(j.match_score) === "fair").length,
    low:       statusFiltered.filter(j => matchBucket(j.match_score) === "low").length,
  }

  const MATCH_FILTERS = [
    { value: "all",       label: "All matches" },
    { value: "excellent", label: "Excellent",  count: matchCounts.excellent, color: "green"  },
    { value: "good",      label: "Good",       count: matchCounts.good,      color: "yellow" },
    { value: "fair",      label: "Fair",       count: matchCounts.fair,      color: "orange" },
    { value: "low",       label: "Low",        count: matchCounts.low,       color: "red"    },
  ] as const

  const STATUS_FILTERS = [
    { value: "all",      label: "All" },
    { value: "new",      label: "New",      count: counts.new },
    { value: "approved", label: "Approved", count: counts.approved },
    { value: "applied",  label: "Applied",  count: counts.applied },
    { value: "pending",  label: "Pending",  count: counts.pending },
    { value: "skipped",  label: "Skipped",  count: counts.skipped },
  ]

  const BLOCKED_DOMAINS = ["wellfound.com"]
  const blockedDomain = (() => {
    try { return BLOCKED_DOMAINS.find(d => new URL(urlInput.trim()).hostname.includes(d)) ?? null }
    catch { return null }
  })()

  const isAnyScraping = scrapingSource !== null
  const scrapeLabel = scrapingSource
    ? `Scraping ${scrapingSource[0].toUpperCase() + scrapingSource.slice(1)}...`
    : "Scrape Jobs"

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Job Feed</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {counts.new} new · {counts.approved} approved · {counts.applied} applied · {counts.pending > 0 ? `${counts.pending} pending · ` : ""}{counts.skipped} skipped
          </p>
        </div>
        <div className="flex items-center gap-2">

          {/* Session chips */}
          <div className="flex items-center gap-1.5">
            {linkedinSession !== null && (
              <SessionChip
                label="LinkedIn"
                icon={<LinkedInIcon />}
                hasSession={linkedinSession.has_session}
                expiresAt={linkedinSession.expires_at}
              />
            )}
            {builtinSession !== null && (
              <SessionChip
                label="Builtin"
                icon={<BuiltinIcon />}
                hasSession={builtinSession.has_session}
                expiresAt={null}
              />
            )}
          </div>

          {counts.new > 0 && (
            <Button variant="outline" size="sm" onClick={handleClearNew} disabled={clearing}
              className="text-destructive border-destructive/30 hover:bg-destructive/10">
              <Trash2 className="h-4 w-4 mr-1.5" />
              Clear new ({counts.new})
            </Button>
          )}
          <Button size="sm" onClick={handleScrapeAll} disabled={isAnyScraping}
            title="Scrapes all enabled sources from Settings."
          >
            {isAnyScraping
              ? <RefreshCw className="h-4 w-4 mr-1.5 animate-spin" />
              : <Search className="h-4 w-4 mr-1.5" />
            }
            {scrapeLabel}
          </Button>
        </div>
      </div>

      {/* Add job from URL */}
      <div className="flex flex-col gap-1.5 mb-4">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Link className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Paste job URL to add (LinkedIn, Greenhouse, Lever, Workday...)"
              className="pl-9"
              value={urlInput}
              onChange={e => setUrlInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !blockedDomain && handleAddFromUrl()}
              disabled={addingUrl}
            />
          </div>
          <Button size="sm" onClick={handleAddFromUrl} disabled={addingUrl || !urlInput.trim() || (!!blockedDomain && !pastedJd.trim())}>
            {addingUrl ? <RefreshCw className="h-4 w-4 mr-1.5 animate-spin" /> : null}
            {addingUrl ? "Adding..." : "Add Job"}
          </Button>
        </div>
        {blockedDomain && (
          <div className="flex flex-col gap-1.5">
            <p className="text-xs text-destructive pl-1">
              {blockedDomain} blocks automated access — paste the job description below.
            </p>
            <textarea
              className="w-full min-h-[120px] rounded-md border border-input bg-background px-3 py-2 text-sm resize-y placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              placeholder="Paste the full job description here..."
              value={pastedJd}
              onChange={e => setPastedJd(e.target.value)}
              disabled={addingUrl}
            />
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by title, company..."
            className="pl-9"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-1">
          {STATUS_FILTERS.map(f => (
            <button
              key={f.value}
              type="button"
              onClick={() => setStatusFilter(f.value)}
              className={cn(
                "px-3 py-1.5 text-sm border rounded-md transition-colors",
                statusFilter === f.value
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-background text-foreground border-input hover:bg-accent"
              )}
            >
              {f.label}
              {"count" in f && f.count !== undefined && f.count > 0 && (
                <span className={cn(
                  "ml-1.5 text-xs rounded-full px-1.5 py-0.5",
                  statusFilter === f.value ? "bg-white/20" : "bg-muted"
                )}>
                  {f.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Match filter */}
      <div className="flex gap-1 mb-4">
        {MATCH_FILTERS.map(f => {
          const active = matchFilter === f.value
          const colorCls = "color" in f ? {
            green:  active ? "bg-green-600  text-white border-green-600"  : "border-green-300  text-green-700  hover:bg-green-50",
            yellow: active ? "bg-yellow-500 text-white border-yellow-500" : "border-yellow-300 text-yellow-700 hover:bg-yellow-50",
            orange: active ? "bg-orange-500 text-white border-orange-500" : "border-orange-300 text-orange-700 hover:bg-orange-50",
            red:    active ? "bg-red-500    text-white border-red-500"    : "border-red-300    text-red-700    hover:bg-red-50",
          }[f.color] : active ? "bg-primary text-primary-foreground border-primary" : "bg-background text-foreground border-input hover:bg-accent"
          return (
            <button
              key={f.value}
              type="button"
              onClick={() => setMatchFilter(f.value)}
              className={cn("px-3 py-1 text-xs border rounded-md transition-colors", colorCls)}
            >
              {f.label}
              {"count" in f && f.count > 0 && (
                <span className={cn("ml-1.5 rounded-full px-1.5 py-0.5", active ? "bg-white/25" : "bg-muted")}>
                  {f.count}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Job list */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <Search className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p className="font-medium">No jobs found</p>
          <p className="text-sm mt-1">
            {jobs.length === 0
              ? "Click \"Scrape Jobs\" to discover new opportunities"
              : "Try adjusting your filters"}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(job => (
            <JobCard key={job.id} job={job} onUpdate={handleJobUpdate} />
          ))}
        </div>
      )}
    </div>
  )
}
