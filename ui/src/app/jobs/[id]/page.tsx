"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { toast } from "sonner"
import {
  ArrowLeft, Sparkles, Send, FileText, ExternalLink,
  ChevronDown, ChevronUp, Loader2, Eye
} from "lucide-react"
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn, STATUS_COLORS, ATS_COLORS } from "@/lib/utils"
import { api, type Job, type ResumeData } from "@/lib/api"

function TailoredResumeView({ resume }: { resume: ResumeData }) {
  return (
    <div className="space-y-5 text-sm">
      {resume.summary && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1.5">Summary</h4>
          <p>{resume.summary}</p>
        </div>
      )}

      {resume.experience?.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Experience</h4>
          <div className="space-y-3">
            {resume.experience.map((exp, i) => (
              <div key={i}>
                <div className="flex justify-between items-baseline">
                  <span className="font-semibold">{exp.title}</span>
                  <span className="text-xs text-muted-foreground">{exp.dates}</span>
                </div>
                <div className="text-muted-foreground text-xs mb-1">{exp.company}</div>
                <ul className="space-y-0.5 pl-3">
                  {exp.bullets?.map((b, bi) => (
                    <li key={bi} className="text-foreground before:content-['•'] before:mr-2 before:text-muted-foreground">{b}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {resume.skills?.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1.5">Skills</h4>
          <div className="flex flex-wrap gap-1.5">
            {resume.skills.map((s, i) => (
              <Badge key={i} className="bg-primary/10 text-primary border-primary/20 border text-xs">{s}</Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [job, setJob] = useState<Job | null>(null)
  const [tailored, setTailored] = useState<ResumeData | null>(null)
  const [loading, setLoading] = useState(true)
  const [tailoring, setTailoring] = useState(false)
  const [applyLoading, setApplyLoading] = useState(false)
  const [coverLetterLoading, setCoverLetterLoading] = useState(false)
  const [showJD, setShowJD] = useState(false)

  useEffect(() => {
    Promise.all([
      api.jobs.get(Number(id)),
      api.jobs.getTailoredData(Number(id)),
    ]).then(([j, td]) => {
      setJob(j)
      setTailored(td.tailored)
    }).catch(() => toast.error("Failed to load job")).finally(() => setLoading(false))
  }, [id])

  async function handleTailor() {
    setTailoring(true)
    try {
      const result = await api.jobs.tailor(Number(id))
      setJob(result.job)
      setTailored(result.tailored)
      toast.success("Resume tailored!")
    } catch (e: any) {
      toast.error(e.message ?? "Tailoring failed")
    } finally {
      setTailoring(false)
    }
  }

  async function handleCoverLetter() {
    setCoverLetterLoading(true)
    try {
      const result = await api.jobs.tailorCoverLetter(Number(id))
      setJob(prev => prev ? { ...prev, cover_letter: result.cover_letter } : prev)
      toast.success("Cover letter generated!")
    } catch {
      toast.error("Failed to generate cover letter")
    } finally {
      setCoverLetterLoading(false)
    }
  }

  async function handleApply() {
    setApplyLoading(true)
    try {
      await api.automation.apply(Number(id))
      toast.success("Application started — check the browser window")
    } catch {
      toast.error("Failed to start application")
    } finally {
      setApplyLoading(false)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  )

  if (!job) return <div className="py-20 text-center text-muted-foreground">Job not found</div>

  return (
    <div>
      <Button variant="ghost" size="sm" className="mb-4 -ml-2" onClick={() => router.back()}>
        <ArrowLeft className="h-4 w-4 mr-1.5" />
        Back
      </Button>

      {/* Job header */}
      <div className="mb-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">{job.title}</h1>
            <p className="text-muted-foreground mt-0.5">
              {job.company}{job.location ? ` · ${job.location}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge className={cn("border", STATUS_COLORS[job.status])}>{job.status}</Badge>
            {job.ats_type !== "unknown" && (
              <Badge className={cn("border", ATS_COLORS[job.ats_type])}>{job.ats_type}</Badge>
            )}
            {job.url && (
              <a href={job.url} target="_blank" rel="noopener noreferrer">
                <Button variant="outline" size="sm">
                  <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                  View Job
                </Button>
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mb-6">
        <Button onClick={handleTailor} disabled={tailoring || !job.jd_text}>
          {tailoring ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Sparkles className="h-4 w-4 mr-1.5" />}
          {tailored ? "Re-tailor Resume" : "Tailor Resume"}
        </Button>
        <Button
          variant="outline"
          disabled={!tailored}
          onClick={() => window.open(`${API_BASE}/api/jobs/${id}/resume-pdf`, "_blank")}
        >
          <Eye className="h-4 w-4 mr-1.5" />
          Preview PDF
        </Button>
        <Button variant="outline" onClick={handleCoverLetter} disabled={coverLetterLoading || !job.jd_text}>
          {coverLetterLoading ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <FileText className="h-4 w-4 mr-1.5" />}
          {job.cover_letter ? "Regenerate Cover Letter" : "Generate Cover Letter"}
        </Button>
        {tailored && (
          <Button
            className="bg-green-600 hover:bg-green-700"
            onClick={handleApply}
            disabled={applyLoading}
          >
            {applyLoading ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Send className="h-4 w-4 mr-1.5" />}
            Apply Now
          </Button>
        )}
      </div>

      <Tabs defaultValue="jd">
        <TabsList>
          <TabsTrigger value="jd">Job Description</TabsTrigger>
          {tailored && <TabsTrigger value="tailored">Resume (text)</TabsTrigger>}
          {job.cover_letter && <TabsTrigger value="cover">Cover Letter</TabsTrigger>}
        </TabsList>

        <TabsContent value="jd" className="mt-4">
          <Card>
            <CardContent className="pt-4">
              {job.jd_text ? (
                <div>
                  <div className={cn("text-sm whitespace-pre-wrap", !showJD && "line-clamp-[20]")}>
                    {job.jd_text}
                  </div>
                  <button
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mt-2"
                    onClick={() => setShowJD(!showJD)}
                  >
                    {showJD ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                    {showJD ? "Show less" : "Show full description"}
                  </button>
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">No job description available.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {tailored && (
          <TabsContent value="tailored" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Tailored Resume</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Generated from your SKILL.md for this specific role · PDF saved to ~/.apply4me/resumes/
                </p>
              </CardHeader>
              <CardContent>
                <TailoredResumeView resume={tailored} />
              </CardContent>
            </Card>
          </TabsContent>
        )}

{job.cover_letter && (
          <TabsContent value="cover" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Cover Letter</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-xs font-mono whitespace-pre-wrap leading-relaxed bg-muted p-4 rounded-md">
                  {job.cover_letter}
                </pre>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
