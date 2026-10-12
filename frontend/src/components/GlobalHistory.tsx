import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { HistoryIcon } from 'lucide-react'
import { assetUrl, request, type GenerationJob } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { active, statusLabel } from '@/components/GenerationUI'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'

interface HistoryJob extends GenerationJob {
  project_name: string
}

/** Which step of the workflow a job belongs to, as the tabs name it. */
const STEP_LABEL: Record<string, string> = {
  master: '2. Nhân vật gốc',
  turnaround: '3. Turnaround',
  concept: '4. Concept',
  enhance: '5. Nâng cấp',
  test: 'Thử kết nối',
}

/** Every generation across every project, reachable from anywhere in the app. */
export default function GlobalHistory({ onOpenProject }: { onOpenProject: (id: string) => void }) {
  const [open, setOpen] = useState(false)
  const [onlyFailed, setOnlyFailed] = useState(false)
  const jobs = useQuery({
    queryKey: ['global-jobs'],
    queryFn: () => request<HistoryJob[]>('/jobs?limit=200'),
    refetchInterval: open ? 2000 : false,
    enabled: open,
  })
  const rows = (jobs.data ?? []).filter((j) => !onlyFailed || ['failed', 'cancelled'].includes(j.status))

  return <>
    <Button
      data-global-history-toggle
      variant="outline"
      size="sm"
      className="fixed bottom-4 left-1/2 z-40 -translate-x-1/2 shadow-lg"
      onClick={() => setOpen(true)}
    >
      <HistoryIcon /> Lịch sử tạo ảnh
    </Button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-h-[90vh] overflow-auto sm:max-w-4xl">
        <DialogTitle>Lịch sử tạo ảnh</DialogTitle>
        <DialogDescription>
          Toàn bộ ảnh đã tạo của mọi dự án, mới nhất trước. Bấm một dòng để mở dự án đó.
        </DialogDescription>
        <label className="text-sm">
          <input type="checkbox" checked={onlyFailed} onChange={(e) => setOnlyFailed(e.target.checked)} /> Chỉ xem job lỗi
        </label>
        {jobs.error && <ErrorAlert error={jobs.error} title="Không tải được lịch sử" />}
        {jobs.isPending && <p className="text-sm text-muted-foreground">Đang tải…</p>}
        {!jobs.isPending && !rows.length && <p className="rounded-lg bg-muted p-6 text-center text-sm">Chưa có job nào.</p>}
        <ul className="space-y-2">
          {rows.map((job) => (
            <li key={job.id}>
              <button
                type="button"
                className="flex w-full items-center gap-3 rounded-lg border p-2 text-left hover:bg-muted"
                onClick={() => { onOpenProject(job.project_id); setOpen(false) }}
              >
                {job.output_asset_ids[0]
                  ? <img src={assetUrl(job.output_asset_ids[0])} alt="" className="size-12 shrink-0 rounded object-cover" />
                  : <span className="size-12 shrink-0 rounded bg-muted" aria-hidden />}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{job.project_name}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {STEP_LABEL[job.purpose] ?? job.purpose} · {job.provider} · {job.model}
                  </span>
                  {job.error_message && <span className="block truncate text-xs text-destructive">{job.error_message}</span>}
                </span>
                <span className="shrink-0 text-right text-xs">
                  <span className={active(job) ? '' : job.status === 'succeeded' ? 'text-emerald-700' : 'text-destructive'}>
                    {statusLabel[job.status] ?? job.status}
                  </span>
                  <time className="block text-muted-foreground" dateTime={job.created_at}>
                    {new Date(job.created_at).toLocaleString('vi-VN')}
                  </time>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  </>
}
