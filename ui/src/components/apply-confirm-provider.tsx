"use client"

import { useEffect, useState } from "react"
import { toast } from "sonner"
import { api } from "@/lib/api"
import { ApplyConfirmDialog } from "@/components/apply-confirm-dialog"

export const PENDING_APPLIES_KEY = "apply4me_pending_applies"

export interface PendingApply {
  jobId: number
  title: string
  company: string
}

export function addPendingApply(apply: PendingApply) {
  const existing: PendingApply[] = JSON.parse(localStorage.getItem(PENDING_APPLIES_KEY) || "[]")
  if (!existing.find(a => a.jobId === apply.jobId)) {
    existing.push(apply)
    localStorage.setItem(PENDING_APPLIES_KEY, JSON.stringify(existing))
  }
}

export function ApplyConfirmProvider() {
  const [queue, setQueue] = useState<PendingApply[]>([])

  function loadPending() {
    const pending: PendingApply[] = JSON.parse(localStorage.getItem(PENDING_APPLIES_KEY) || "[]")
    if (pending.length > 0) setQueue(pending)
  }

  useEffect(() => {
    window.addEventListener("focus", loadPending)
    return () => window.removeEventListener("focus", loadPending)
  }, [])

  async function handleYes() {
    const current = queue[0]
    try {
      await api.jobs.markApplied(current.jobId)
      toast.success(`Marked "${current.title}" as applied`)
    } catch {
      toast.error("Failed to mark as applied")
    }
    dismiss()
  }

  function handleNo() {
    dismiss()
  }

  function dismiss() {
    const next = queue.slice(1)
    setQueue(next)
    localStorage.setItem(PENDING_APPLIES_KEY, JSON.stringify(next))
  }

  if (queue.length === 0) return null

  const current = queue[0]
  return (
    <ApplyConfirmDialog
      title={current.title}
      company={current.company}
      onYes={handleYes}
      onNo={handleNo}
    />
  )
}
