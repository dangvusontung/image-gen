import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2Icon, LoaderCircleIcon, XCircleIcon, XIcon } from 'lucide-react'
import { request, type GenerationJob } from '@/api/client'
import { active, statusLabel } from '@/components/GenerationUI'
import { Button } from '@/components/ui/button'

const PURPOSE: Record<string, string> = {
  master: 'Nhân vật gốc', turnaround: 'Turnaround', concept: 'Concept', enhance: 'Nâng cấp', test: 'Thử kết nối',
}
const DISMISS_AFTER_MS = 10_000
const purposeLabel = (purpose: string) => PURPOSE[purpose] ?? purpose

interface Finished {
  id: string
  purpose: string
  status: string
  error: string | null
  at: number
}

/** Floating panel: what is generating now, and a short-lived note as each job finishes. */
export default function GenerationMonitor({ projectId }: { projectId: string }) {
  // Same key and URL as the history step, so both share one poll.
  const jobs = useQuery({
    queryKey: ['jobs', projectId],
    queryFn: () => request<GenerationJob[]>(`/projects/${projectId}/jobs?limit=500`),
    refetchInterval: 1500,
  })
  const [finished, setFinished] = useState<Finished[]>([])
  // Jobs already finished when the panel opened: the backlog, never announced.
  const backlog = useRef<Set<string> | null>(null)
  const announced = useRef(new Set<string>())
  const running = (jobs.data ?? []).filter(active)

  useEffect(() => {
    if (!jobs.data) return
    const done = jobs.data.filter((job) => !active(job))
    if (backlog.current === null) {
      backlog.current = new Set(done.map((job) => job.id))
      return
    }
    // Anything finished that was not in the backlog finished on our watch — even if it was
    // too quick to ever be caught mid-poll.
    const fresh = done.filter((job) => !backlog.current!.has(job.id) && !announced.current.has(job.id))
    if (!fresh.length) return
    for (const job of fresh) announced.current.add(job.id)
    setFinished((prev) => [
      ...fresh.map((job) => ({ id: job.id, purpose: job.purpose, status: job.status, error: job.error_message, at: Date.now() })),
      ...prev,
    ].slice(0, 5))
  }, [jobs.data])

  useEffect(() => {
    if (!finished.length) return
    const timer = setInterval(
      () => setFinished((prev) => prev.filter((f) => Date.now() - f.at < DISMISS_AFTER_MS)),
      500,
    )
    return () => clearInterval(timer)
  }, [finished.length])

  if (!running.length && !finished.length) return null

  return (
    <aside
      role="region"
      aria-label="Tiến trình tạo ảnh"
      className="fixed right-4 bottom-4 z-50 w-72 space-y-2 rounded-xl border bg-popover p-3 text-sm shadow-lg"
    >
      {running.length > 0 && (
        <>
          <p className="flex items-center gap-2 font-medium">
            <LoaderCircleIcon className="size-4 animate-spin" aria-hidden />
            Đang tạo {running.length} ảnh
          </p>
          <ul className="space-y-1">
            {running.map((job) => (
              <li key={job.id} className="flex items-center justify-between gap-2 text-muted-foreground">
                <span className="truncate">{purposeLabel(job.purpose)}</span>
                <span className="shrink-0 text-xs">{statusLabel[job.status] ?? job.status}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {finished.length > 0 && (
        <ul aria-live="polite" className="space-y-1 border-t pt-2">
          {finished.map((job) => (
            <li key={job.id} className="flex items-start gap-2">
              {job.status === 'succeeded'
                ? <CheckCircle2Icon className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
                : <XCircleIcon className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />}
              <span className="min-w-0 flex-1">
                {purposeLabel(job.purpose)} · {statusLabel[job.status] ?? job.status}
                {job.status !== 'succeeded' && job.error && (
                  <span className="block truncate text-xs text-muted-foreground">{job.error}</span>
                )}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="size-5 shrink-0"
                aria-label={`Ẩn thông báo ${purposeLabel(job.purpose)}`}
                onClick={() => setFinished((prev) => prev.filter((f) => f.id !== job.id))}
              >
                <XIcon />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
