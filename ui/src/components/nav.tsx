"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { BriefcaseIcon, FileTextIcon, SettingsIcon } from "lucide-react"

const links = [
  { href: "/", label: "Jobs", icon: BriefcaseIcon },
  { href: "/resume", label: "Resume", icon: FileTextIcon },
  { href: "/settings", label: "Settings", icon: SettingsIcon },
]

export function Nav() {
  const pathname = usePathname()
  return (
    <nav className="border-b bg-white">
      <div className="container mx-auto px-4 max-w-6xl flex items-center justify-between h-14">
        <Link href="/" className="font-bold text-lg text-primary">
          appy4me
        </Link>
        <div className="flex items-center gap-1">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                pathname === href || (href !== "/" && pathname.startsWith(href))
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  )
}
