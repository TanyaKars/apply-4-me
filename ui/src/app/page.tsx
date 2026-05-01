"use client"

import { useEffect, useState, useCallback } from "react"
import { toast } from "sonner"
import {
  RefreshCw, Search, Wifi, WifiOff, Trash2, Clock
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { JobCard } from "@/components/job-card"
import { api, type Job } from "@/lib/api"

function useSessionCountdown(expiresAt: number | null) {
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null)

  useEffect(() => {
    if (!expiresAt) { setSecondsLeft(null); return }
    const tick = () => {
      const diff = Math.floor(expiresAt - Date.now() / 1000)
      setSecondsLeft(diff > 0 ? diff : 0)
    }
    tick()
    const id = setInterval(tick, 60_000)
    return () => clearInterval(id)
  }, [expiresAt])

  if (secondsLeft === null) return null
  if (secondsLeft <= 0) return "Expired"
  const h = Math.floor(secondsLeft / 3600)
  const m = Math.floor((secondsLeft % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

export default function HomePage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [scraping, setScraping] = useState(false)
  const [statusFilter, setStatusFilter] = useState("all")
  const [search, setSearch] = useState("")
  const [session, setSession] = useState<{ has_session: boolean; expires_at: number | null } | null>(null)
  const [clearing, setClearing] = useState(false)
  const [scrapeMsg, setScrapeMsg] = useState("")

  const countdown = useSessionCountdown(session?.expires_at ?? null)

  const loadJobs = useCallback(async () => {
    try {
      const status = statusFilter === "all" ? undefined : statusFilter
      const data = await api.jobs.list(status)
      setJobs(data)
    } catch {
      toast.error("Failed to load jobs")
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => { loadJobs() }, [loadJobs])

  useEffect(() => {
    api.automation.sessionStatus()
      .then(s => setSession({ has_session: s.has_session, expires_at: s.expires_at }))
      .catch(() => setSession({ has_session: false, expires_at: null }))
  }, [])

  async function handleScrape() {
    if (!session?.has_session) {
      toast.error("LinkedIn session expired or missing — go to Settings to re-authenticate.")
      return
    }
    setScraping(true)
    try {
      const saved = localStorage.getItem("apply4me_config")
      const cfg = saved ? JSON.parse(saved) : {}
      const search = cfg.search ?? {}
      const keywords = search.keywords?.length ? search.keywords : ["QA Engineer", "SDET"]
      const country = search.country ?? ""
      const city = search.city ?? ""
      const workTypes: string[] = search.work_types ?? []
      const location = city && country ? `${city}, ${country}` : country || "Remote"

      await api.automation.scrape({
        keywords,
        country,
        city,
        date_posted: search.date_posted ?? "past_week",
        work_types: workTypes,
        max_applicants: search.max_applicants ?? null,
        easy_apply_only: search.easy_apply_only ?? false,
      })

      const wtLabel = workTypes.length ? workTypes.join(", ") : "any type"
      setScrapeMsg(`${keywords.join(", ")} · ${location} · ${wtLabel}`)

      const poll = async () => {
        try {
          const status = await api.automation.scrapeStatus()
          if (status.running) {
            setTimeout(poll, 5000)
          } else {
            await loadJobs()
            setScraping(false)
            setScrapeMsg("")
            toast.success("Scrape finished — job list updated")
          }
        } catch {
          setScraping(false)
          setScrapeMsg("")
        }
      }
      setTimeout(poll, 5000)
    } catch {
      toast.error("Failed to start scrape")
      setScraping(false)
    }
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

  function handleJobUpdate(updated: Job) {
    setJobs(prev => prev.map(j => j.id === updated.id ? updated : j))
  }

  const filtered = jobs.filter(j => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      j.title.toLowerCase().includes(q) ||
      j.company.toLowerCase().includes(q) ||
      (j.location ?? "").toLowerCase().includes(q)
    )
  })

  const counts = {
    new: jobs.filter(j => j.status === "new").length,
    approved: jobs.filter(j => j.status === "approved").length,
    applied: jobs.filter(j => j.status === "applied").length,
    skipped: jobs.filter(j => j.status === "skipped").length,
  }

  const STATUS_FILTERS = [
    { value: "all", label: "All" },
    { value: "new", label: "New", count: counts.new },
    { value: "approved", label: "Approved", count: counts.approved },
    { value: "applied", label: "Applied", count: counts.applied },
    { value: "skipped", label: "Skipped", count: counts.skipped },
  ]

  const hasSession = session?.has_session ?? null
  const sessionExpiring = countdown !== null && countdown !== "Expired" &&
    session?.expires_at && (session.expires_at - Date.now() / 1000) < 3600

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Job Feed</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {counts.new} new · {counts.approved} approved · {counts.applied} applied · {counts.skipped} skipped
          </p>
        </div>
        <div className="flex items-center gap-2">
          {session !== null && (
            <span className={cn(
              "flex items-center gap-1 text-xs",
              hasSession
                ? sessionExpiring ? "text-orange-500" : "text-green-600"
                : "text-red-500"
            )}>
              {hasSession ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
              {hasSession
                ? countdown
                  ? <><Clock className="h-3 w-3 ml-0.5" />{countdown}</>
                  : "LinkedIn connected"
                : "No session — go to Settings"}
            </span>
          )}
          {counts.new > 0 && (
            <Button variant="outline" size="sm" onClick={handleClearNew} disabled={clearing}
              className="text-destructive border-destructive/30 hover:bg-destructive/10">
              <Trash2 className="h-4 w-4 mr-1.5" />
              Clear new ({counts.new})
            </Button>
          )}
          <Button size="sm" onClick={handleScrape} disabled={scraping}
            title="Searches LinkedIn for new jobs matching your settings. Already saved jobs won't be duplicated."
          >
            {scraping
              ? <RefreshCw className="h-4 w-4 mr-1.5 animate-spin" />
              : <Search className="h-4 w-4 mr-1.5" />
            }
            {scraping
              ? scrapeMsg ? `Scraping: ${scrapeMsg}` : "Scraping..."
              : "Scrape Jobs"
            }
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
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
