"use client"

import { useEffect, useState, useRef } from "react"
import { toast } from "sonner"
import { FileDown, Upload, Loader2, RefreshCw, FileText } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { api } from "@/lib/api"

export default function ResumePage() {
  const [skillMd, setSkillMd] = useState<{ content: string; path: string; exists: boolean } | null>(null)
  const [settings, setSettings] = useState({ template: "modern", include_photo: false, photo_path: "" })
  const [generating, setGenerating] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const photoRef = useRef<HTMLInputElement>(null)

  async function load() {
    const [sm, s] = await Promise.all([api.resume.skillMd(), api.resume.settings()])
    setSkillMd(sm)
    setSettings(s)
  }

  useEffect(() => { load().catch(() => {}) }, [])

  async function handleSaveSettings() {
    try {
      await api.resume.saveSettings(settings)
      toast.success("Saved")
    } catch {
      toast.error("Failed to save")
    }
  }

  async function handleGeneratePdf() {
    setGenerating(true)
    try {
      await api.resume.saveSettings(settings)
      const result = await api.resume.generatePdf()
      toast.success(`PDF saved to ${result.pdf_path}`)
    } catch (e: any) {
      toast.error(e.message ?? "Failed to generate PDF")
    } finally {
      setGenerating(false)
    }
  }

  async function handleRefresh() {
    setRefreshing(true)
    try {
      const sm = await api.resume.skillMd()
      setSkillMd(sm)
      toast.success("Refreshed")
    } catch {
      toast.error("Failed to refresh")
    } finally {
      setRefreshing(false)
    }
  }

  async function handlePhotoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const form = new FormData()
    form.append("file", file)
    try {
      const res = await fetch("http://localhost:8000/api/resume/upload-photo", { method: "POST", body: form })
      const data = await res.json()
      setSettings(s => ({ ...s, photo_path: data.photo_path }))
      toast.success("Photo uploaded")
    } catch {
      toast.error("Failed to upload photo")
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Resume</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Edit your SKILL.md in VS Code — Claude reads it when tailoring
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1.5" />}
            Refresh
          </Button>
          <Button size="sm" onClick={handleGeneratePdf} disabled={generating || !skillMd?.exists}>
            {generating ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <FileDown className="h-4 w-4 mr-1.5" />}
            Preview PDF
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* SKILL.md preview — takes 2/3 width */}
        <div className="col-span-2">
          <Card className="h-full">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    SKILL.md
                  </CardTitle>
                  {skillMd && (
                    <CardDescription className="mt-0.5 font-mono text-xs">{skillMd.path}</CardDescription>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {!skillMd ? (
                <div className="flex items-center gap-2 text-muted-foreground text-sm py-8 justify-center">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading...
                </div>
              ) : !skillMd.exists ? (
                <div className="text-center py-12 text-muted-foreground">
                  <FileText className="h-10 w-10 mx-auto mb-3 opacity-30" />
                  <p className="font-medium">No SKILL.md found</p>
                  <p className="text-sm mt-1">
                    Create <code className="bg-muted px-1 rounded">{skillMd.path}</code> in VS Code,<br />
                    or use "Parse from Resume" to generate it automatically.
                  </p>
                </div>
              ) : (
                <pre className="text-xs font-mono whitespace-pre-wrap leading-relaxed text-foreground bg-muted/40 rounded-md p-4 overflow-auto max-h-[600px]">
                  {skillMd.content}
                </pre>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Settings sidebar */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">PDF Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label>Template</Label>
                <Select
                  value={settings.template}
                  onValueChange={v => setSettings(s => ({ ...s, template: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["modern", "classic", "minimal"].map(t => (
                      <SelectItem key={t} value={t} className="capitalize">{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <Label>Photo</Label>
                  <label className="flex items-center gap-1.5 text-sm text-muted-foreground cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.include_photo}
                      onChange={e => setSettings(s => ({ ...s, include_photo: e.target.checked }))}
                    />
                    Include in PDF
                  </label>
                </div>
                <div className="flex gap-2">
                  <Input
                    value={settings.photo_path}
                    onChange={e => setSettings(s => ({ ...s, photo_path: e.target.value }))}
                    placeholder="/path/to/photo.jpg"
                    className="text-xs"
                  />
                  <Button variant="outline" size="icon" onClick={() => photoRef.current?.click()}>
                    <Upload className="h-4 w-4" />
                  </Button>
                  <input ref={photoRef} type="file" accept="image/*" className="hidden" onChange={handlePhotoUpload} />
                </div>
              </div>

              <Button size="sm" className="w-full" onClick={handleSaveSettings}>
                Save Settings
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Parse from Resume</CardTitle>
              <CardDescription>
                Give a path to your existing PDF or DOCX — Claude converts it to SKILL.md
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ParseFromResume onDone={load} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function ParseFromResume({ onDone }: { onDone: () => void }) {
  const [path, setPath] = useState("")
  const [loading, setLoading] = useState(false)

  async function handleParse() {
    if (!path.trim()) return
    setLoading(true)
    try {
      const result = await api.resume.parseSource(path.trim())
      toast.success(`SKILL.md written to ${result.path}`)
      onDone()
    } catch (e: any) {
      toast.error(e.message ?? "Parse failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label>Resume file path</Label>
        <Input
          value={path}
          onChange={e => setPath(e.target.value)}
          placeholder="/Users/you/resume.pdf"
          className="text-xs font-mono"
        />
      </div>
      <Button
        size="sm"
        className="w-full"
        onClick={handleParse}
        disabled={loading || !path.trim()}
      >
        {loading ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <FileText className="h-4 w-4 mr-1.5" />}
        {loading ? "Parsing..." : "Parse → SKILL.md"}
      </Button>
      <p className="text-xs text-muted-foreground">
        This overwrites your current SKILL.md. Review and edit it in VS Code afterwards.
      </p>
    </div>
  )
}
