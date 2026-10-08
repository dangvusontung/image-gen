import { AlertCircleIcon } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

export function ErrorAlert({ title = 'Có lỗi xảy ra', error }: { title?: string; error: unknown }) {
  const message = error instanceof Error ? error.message : String(error)
  return (
    <Alert variant="destructive">
      <AlertCircleIcon />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="whitespace-pre-line">{message}</AlertDescription>
    </Alert>
  )
}
