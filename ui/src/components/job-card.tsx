"use client"

import { useState } from "react"
import Link from "next/link"
import { toast } from "sonner"
import { Check, X, ExternalLink, MapPin, Building2, RotateCcw } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn, STATUS_COLORS, SOURCE_COLORS, SOURCE_LABELS, getJobSource, formatDate } from "@/lib/utils"
import { api, type Job } from "@/lib/api"

interface JobCardProps {
  job: Job
  onUpdate: (job: Job) => void
}

export function JobCard({ job, onUpdate }: JobCardProps) {
  const [loading, setLoading] = useState<"approve" | "skip" | "reconsider" | null>(null)

  async function handleApprove() {
    setLoading("approve")
    try {
      const updated = await api.jobs.approve(job.id)
      onUpdate(updated)
      toast.success("Job approved")
    } catch {
      toast.error("Failed to approve job")
    } finally {
      setLoading(null)
    }
  }

  async function handleSkip() {
    setLoading("skip")
    try {
      const updated = await api.jobs.skip(job.id)
      onUpdate(updated)
      toast.success("Job skipped")
    } catch {
      toast.error("Failed to skip job")
    } finally {
      setLoading(null)
    }
  }

  async function handleUnskip() {
    setLoading("reconsider")
    try {
      const updated = await api.jobs.unskip(job.id)
      onUpdate(updated)
      toast.success("Job moved back to new")
    } catch {
      toast.error("Failed to unskip job")
    } finally {
      setLoading(null)
    }
  }

  const source = getJobSource(job.url)
  const sourceLabel = SOURCE_LABELS[source] ?? source
  const sourceColor = SOURCE_COLORS[source] ?? "bg-gray-50 text-gray-500 border-gray-200"

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <Link
                href={`/jobs/${job.id}`}
                className="font-semibold text-base hover:text-primary truncate"
              >
                {job.title}
              </Link>
              <Badge className={cn("text-xs border", STATUS_COLORS[job.status])}>
                {job.status}
              </Badge>
              <Badge className={cn("text-xs border", sourceColor)}>
                {sourceLabel}
              </Badge>
            </div>
            <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Building2 className="h-3.5 w-3.5" />
                {job.company}
              </span>
              {job.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" />
                  {job.location}
                </span>
              )}
              <span className="text-xs">{formatDate(job.created_at)}</span>
            </div>
            {job.jd_text && (
              <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2">
                {job.jd_text.slice(0, 200)}...
              </p>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {job.url && (
              <a href={job.url} target="_blank" rel="noopener noreferrer">
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <ExternalLink className="h-3.5 w-3.5" />
                </Button>
              </a>
            )}
            {job.status === "new" && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 border-red-200 text-red-600 hover:bg-red-50"
                  onClick={handleSkip}
                  disabled={loading !== null}
                >
                  <X className="h-3.5 w-3.5 mr-1" />
                  Skip
                </Button>
                <Button
                  size="sm"
                  className="h-8"
                  onClick={handleApprove}
                  disabled={loading !== null}
                >
                  <Check className="h-3.5 w-3.5 mr-1" />
                  Approve
                </Button>
              </>
            )}
            {job.status === "approved" && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 border-red-200 text-red-600 hover:bg-red-50"
                  onClick={handleSkip}
                  disabled={loading !== null}
                >
                  <X className="h-3.5 w-3.5 mr-1" />
                  Skip
                </Button>
                <Link href={`/jobs/${job.id}`}>
                  <Button size="sm" className="h-8">
                    View & Apply
                  </Button>
                </Link>
              </>
            )}
            {job.status === "skipped" && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8"
                  onClick={handleUnskip}
                  disabled={loading !== null}
                >
                  <RotateCcw className="h-3.5 w-3.5 mr-1" />
                  Unskip
                </Button>
                <Link href={`/jobs/${job.id}`}>
                  <Button size="sm" variant="outline" className="h-8">
                    View
                  </Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
