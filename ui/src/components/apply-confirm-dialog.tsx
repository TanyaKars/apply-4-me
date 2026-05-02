"use client"

import { CheckCircle2, XCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

interface ApplyConfirmDialogProps {
  title: string
  company: string
  onYes: () => void
  onNo: () => void
}

export function ApplyConfirmDialog({ title, company, onYes, onNo }: ApplyConfirmDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <Card className="w-full max-w-sm shadow-xl">
        <CardContent className="pt-6 pb-5 px-6 space-y-4">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">Did you apply for</p>
            <p className="text-lg font-bold leading-tight">{title}</p>
            <p className="text-sm text-muted-foreground">{company}</p>
          </div>
          <div className="flex gap-2 pt-1">
            <Button
              variant="outline"
              className="flex-1 border-red-200 text-red-600 hover:bg-red-50"
              onClick={onNo}
            >
              <XCircle className="h-4 w-4 mr-1.5" />
              No
            </Button>
            <Button
              className="flex-1 bg-green-600 hover:bg-green-700"
              onClick={onYes}
            >
              <CheckCircle2 className="h-4 w-4 mr-1.5" />
              Yes, applied!
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
