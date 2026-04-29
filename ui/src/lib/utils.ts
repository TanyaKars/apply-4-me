import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—"
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric"
  })
}

export const STATUS_COLORS: Record<string, string> = {
  new: "bg-blue-50 text-blue-700 border-blue-200",
  approved: "bg-green-50 text-green-700 border-green-200",
  skipped: "bg-gray-50 text-gray-500 border-gray-200",
  applied: "bg-purple-50 text-purple-700 border-purple-200",
  rejected: "bg-red-50 text-red-600 border-red-200",
}

export const ATS_COLORS: Record<string, string> = {
  greenhouse: "bg-emerald-50 text-emerald-700 border-emerald-200",
  lever: "bg-orange-50 text-orange-700 border-orange-200",
  ashby: "bg-violet-50 text-violet-700 border-violet-200",
  workday: "bg-cyan-50 text-cyan-700 border-cyan-200",
  easy_apply: "bg-blue-50 text-blue-700 border-blue-200",
  unknown: "bg-gray-50 text-gray-500 border-gray-200",
}
