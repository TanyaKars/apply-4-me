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
  pending: "bg-amber-50 text-amber-700 border-amber-200",
}

export const SOURCE_LABELS: Record<string, string> = {
  linkedin: "LinkedIn",
  builtin: "Builtin",
  indeed: "Indeed",
  jobright: "Jobright",
  wellfound: "Wellfound",
}

export const SOURCE_COLORS: Record<string, string> = {
  linkedin: "bg-blue-50 text-blue-700 border-blue-200",
  builtin: "bg-violet-50 text-violet-700 border-violet-200",
  indeed: "bg-indigo-50 text-indigo-700 border-indigo-200",
  jobright: "bg-emerald-50 text-emerald-700 border-emerald-200",
  wellfound: "bg-orange-50 text-orange-700 border-orange-200",
}

export function getJobSource(url: string): string {
  if (url.includes("linkedin.com")) return "linkedin"
  if (url.includes("builtin.com")) return "builtin"
  if (url.includes("indeed.com")) return "indeed"
  if (url.includes("jobright.ai")) return "jobright"
  if (url.includes("wellfound.com") || url.includes("angel.co")) return "wellfound"
  return "unknown"
}

export const ATS_LABELS: Record<string, string> = {
  greenhouse: "Greenhouse",
  lever: "Lever",
  ashby: "Ashby",
  workday: "Workday",
  icims: "iCIMS",
  taleo: "Taleo",
  smartrecruiters: "SmartRecruiters",
  jobvite: "Jobvite",
  brassring: "BrassRing",
  successfactors: "SuccessFactors",
  easy_apply: "Easy Apply",
  external: "External",
  unknown: "Unknown ATS",
}

export const ATS_COLORS: Record<string, string> = {
  greenhouse: "bg-emerald-50 text-emerald-700 border-emerald-200",
  lever: "bg-orange-50 text-orange-700 border-orange-200",
  ashby: "bg-violet-50 text-violet-700 border-violet-200",
  workday: "bg-cyan-50 text-cyan-700 border-cyan-200",
  icims: "bg-teal-50 text-teal-700 border-teal-200",
  taleo: "bg-amber-50 text-amber-700 border-amber-200",
  smartrecruiters: "bg-indigo-50 text-indigo-700 border-indigo-200",
  jobvite: "bg-pink-50 text-pink-700 border-pink-200",
  brassring: "bg-rose-50 text-rose-700 border-rose-200",
  successfactors: "bg-sky-50 text-sky-700 border-sky-200",
  easy_apply: "bg-blue-50 text-blue-700 border-blue-200",
  external: "bg-slate-50 text-slate-600 border-slate-200",
  unknown: "bg-gray-50 text-gray-500 border-gray-200",
}
