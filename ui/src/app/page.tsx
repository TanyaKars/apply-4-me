"use client"

import { useEffect, useState, useCallback } from "react"
import { toast } from "sonner"
import {
  RefreshCw, Search, Wifi, WifiOff, Trash2
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { JobCard } from "@/components/job-card"
import { api, type Job, type JobStatus } from "@/lib/api"

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: "all", label: "All Jobs" },
  { value: "new", label: "New" },
  { value: "approved", label: "Approved" },
  { value: "applied", label: "Applied" },
  { value: "skipped", label: "Skipped" },
]

export default function HomePage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [scraping, setScraping] = useState(false)
  const [statusFilter, setStatusFilter] = useState("all")
  const [search, setSearch] = useState("")
  const [hasSession, setHasSession] = useState<boolean | null>(null)
  const [clearing, setClearing] = useState(false)

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
      .then(s => setHasSession(s.has_session))
      .catch(() => setHasSession(false))
  }, [])

  async function handleScrape() {
    if (!hasSession) {
      toast.error("No LinkedIn session. Set up session in Settings first.")
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
      })

      const wtLabel = workTypes.length ? workTypes.join(", ") : "any type"
      toast.success(`Scraping: ${keywords.join(", ")} · ${location} · ${wtLabel}`)
      setTimeout(() => { loadJobs(); setScraping(false) }, 5000)
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
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Job Feed</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {counts.new} new · {counts.approved} approved · {counts.applied} applied
          </p>
        </div>
        <div className="flex items-center gap-2">
          {hasSession !== null && (
            <span className={`flex items-center gap-1 text-xs ${hasSession ? "text-green-600" : "text-orange-500"}`}>
              {hasSession ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
              {hasSession ? "LinkedIn connected" : "No session"}
            </span>
          )}
          <Button variant="outline" size="sm" onClick={loadJobs}>
            <RefreshCw className="h-4 w-4 mr-1.5" />
            Refresh
          </Button>
          {counts.new > 0 && (
            <Button variant="outline" size="sm" onClick={handleClearNew} disabled={clearing}
              className="text-destructive border-destructive/30 hover:bg-destructive/10">
              <Trash2 className="h-4 w-4 mr-1.5" />
              Clear new ({counts.new})
            </Button>
          )}
          <Button size="sm" onClick={handleScrape} disabled={scraping}>
            {scraping ? (
              <RefreshCw className="h-4 w-4 mr-1.5 animate-spin" />
            ) : (
              <Search className="h-4 w-4 mr-1.5" />
            )}
            {scraping ? "Scraping..." : "Scrape Jobs"}
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
