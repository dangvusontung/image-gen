import { useEffect, useState } from 'react'
import { Clock3Icon, LoaderCircleIcon } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { assetUrl, downloadUrl, request, type GenerationJob } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'

export const active = (job: { status: string }) => ['queued', 'submitting', 'running'].includes(job.status)
export const statusLabel: Record<string, string> = {
  queued: 'Đang chờ', submitting: 'Đang gửi', running: 'Đang tạo',
  succeeded: 'Hoàn tất', failed: 'Lỗi', cancelled: 'Đã huỷ',
}
export const costLabel = (cost: number | null | undefined) => cost == null ? 'Chưa có giá ước tính' : `~$${cost.toFixed(3)}`

export function JobStatus({ job }: { job: { status: string } }) {
  const processing = ['submitting', 'running'].includes(job.status)
  return <span className="inline-flex items-center gap-2">
    {processing && <LoaderCircleIcon aria-hidden="true" className="size-4 shrink-0 animate-spin motion-reduce:animate-none text-primary" />}
    {job.status === 'queued' && <Clock3Icon aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />}
    {statusLabel[job.status] ?? job.status}
  </span>
}

export function JobPlaceholder({ job }: { job: { status: string } }) {
  if (!active(job)) return null
  return <div aria-busy="true" className="flex aspect-[3/4] flex-col items-center justify-center gap-3 rounded-lg border bg-muted text-sm">
    <JobStatus job={job} />
    <p className="text-xs text-muted-foreground">{job.status === 'queued' ? 'Ảnh sẽ được tạo khi có lượt trống.' : 'Ảnh sẽ hiển thị khi hoàn tất.'}</p>
  </div>
}

export function useGenerationAction(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ path, data, method = 'POST' }: { path: string; data?: unknown; method?: string }) =>
      request(path, { method, headers: { 'Content-Type': 'application/json' }, body: data === undefined ? undefined : JSON.stringify(data) }),
    onSuccess: () => {
      for (const key of [['workflow', projectId], ['concepts', projectId], ['enhancements', projectId], ['jobs', projectId], ['projects'], ['spend'], ['enhance-plan', projectId]]) {
        qc.invalidateQueries({ queryKey: key })
      }
    },
  })
}

export function ImagePreview({ assetId, title = 'Ảnh nhân vật', compareAssetId }: { assetId: string; title?: string; compareAssetId?: string }) {
  const [open, setOpen] = useState(false)
  return <>
    <button type="button" onClick={() => setOpen(true)} className="block w-full cursor-zoom-in rounded-lg focus-visible:ring-2" aria-label={`Xem lớn: ${title}`}>
      <img src={assetUrl(assetId)} alt={title} loading="lazy" className="aspect-[3/4] w-full rounded-lg bg-muted object-contain" />
    </button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-h-[95vh] overflow-auto sm:max-w-6xl">
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{compareAssetId ? 'So sánh ảnh nguồn với bản nâng cấp ở kích thước đầy đủ.' : 'Ảnh gốc, không phải ảnh cắt từ bảng ảnh.'}</DialogDescription>
        <div className={compareAssetId ? 'grid gap-4 md:grid-cols-2' : ''}>
          {compareAssetId && <figure><figcaption>Trước</figcaption><img src={assetUrl(compareAssetId)} alt="Ảnh nguồn trước nâng cấp" className="max-h-[75vh] w-full object-contain" /></figure>}
          <figure>{compareAssetId && <figcaption>Sau</figcaption>}<img src={assetUrl(assetId)} alt={title} className="max-h-[75vh] w-full object-contain" /></figure>
        </div>
        <DownloadLinks assetId={assetId} />
      </DialogContent>
    </Dialog>
  </>
}

export function DownloadLinks({ assetId }: { assetId: string }) {
  return <div className="flex flex-wrap gap-3 text-xs underline">
    <a href={downloadUrl(assetId)}>Tải gốc</a><a href={downloadUrl(assetId, 'png')}>PNG</a><a href={downloadUrl(assetId, 'jpeg')}>JPEG</a>
  </div>
}

export function JobDetails({ job, projectId }: { job: GenerationJob; projectId: string }) {
  const action = useGenerationAction(projectId)
  return <div className="space-y-2 text-sm">
    <p role="status" className="flex flex-wrap items-center gap-2"><JobStatus job={job} />{active(job) && <span>· Lần thử {job.attempts}/{job.max_attempts}</span>}</p>
    {job.error_message && <p role="alert" className="text-destructive">{job.error_message}</p>}
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-muted-foreground">{job.provider} · {job.model} · {costLabel(job.actual_cost_usd ?? job.estimated_cost_usd)}</span>
      {active(job) && <Button size="sm" variant="outline" disabled={action.isPending || job.cancel_requested} onClick={() => action.mutate({ path: `/jobs/${job.id}/cancel` })}>{job.cancel_requested ? 'Đang huỷ' : 'Huỷ'}</Button>}
      {['failed', 'cancelled'].includes(job.status) && <Button size="sm" variant="outline" disabled={action.isPending} onClick={() => action.mutate({ path: `/jobs/${job.id}/retry` })}>Thử lại job</Button>}
    </div>
    {action.error && <ErrorAlert error={action.error} title="Không thực hiện được" />}
    <details className="text-xs"><summary>Prompt và tham chiếu đã sử dụng</summary>
      <p className="mt-2 whitespace-pre-wrap break-words">{job.prompt}</p>
      <p className="mt-2">{job.reference_asset_ids.length} ảnh tham chiếu · {job.id}</p>
    </details>
  </div>
}

export function PromptEditor({ projectId, name }: { projectId: string; name: string }) {
  const qc = useQueryClient()
  const [body, setBody] = useState('')
  const key = ['prompt', projectId, name]
  const path = `/prompts/${name}?project_id=${projectId}`
  const prompt = useQuery({ queryKey: key, queryFn: () => request<{ body: string }>(path) })
  useEffect(() => { if (prompt.data) setBody(prompt.data.body) }, [prompt.data])
  const save = useMutation({ mutationFn: (value: string | null) => request(path, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ body: value }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }) })
  return <details className="space-y-3 rounded-lg border p-4"><summary>Chỉnh sửa prompt</summary>
    {prompt.error && <ErrorAlert error={prompt.error} title="Không tải được prompt" />}
    <Textarea aria-label={`Prompt ${name}`} rows={6} value={body} onChange={e => setBody(e.target.value)} />
    <div className="flex gap-2"><Button disabled={save.isPending || !body.trim()} onClick={() => save.mutate(body)}>Lưu prompt</Button>
      <Button variant="outline" disabled={save.isPending} onClick={() => save.mutate(null)}>Đặt lại mặc định</Button></div>
    {save.error && <ErrorAlert error={save.error} title="Không lưu được prompt" />}
    {save.isSuccess && <p role="status">Đã lưu prompt.</p>}
    <p className="text-xs">Lưu thay đổi trước khi tạo ảnh. Lịch sử job giữ nguyên prompt đã dùng.</p>
  </details>
}
