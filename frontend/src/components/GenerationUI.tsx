import { useEffect, useState } from 'react'
import { ChevronLeftIcon, ChevronRightIcon, Clock3Icon, LoaderCircleIcon, MaximizeIcon, ZoomInIcon, ZoomOutIcon } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { assetUrl, downloadUrl, request, useProviders, type GenerationJob } from '@/api/client'
import { useFavouriteModels } from '@/lib/favourites'
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

export interface GalleryImage {
  assetId: string
  title: string
}

const ZOOM_MIN = 1
const ZOOM_MAX = 4
const ZOOM_STEP = 0.5

export function ImagePreview({ assetId, title = 'Ảnh nhân vật', compareAssetId, gallery }: {
  assetId: string
  title?: string
  compareAssetId?: string
  /** Images to step through with ‹ › while enlarged; `assetId` is where it opens. */
  gallery?: GalleryImage[]
}) {
  const [open, setOpen] = useState(false)
  const items = gallery?.length ? gallery : [{ assetId, title }]
  // Keep the selected asset stable when newly completed jobs change the gallery order.
  const [selectedAssetId, setSelectedAssetId] = useState(assetId)
  const index = Math.max(0, items.findIndex((i) => i.assetId === selectedAssetId))
  // Comparing before/after already fills the dialog, so paging is offered only on its own.
  const canPage = !compareAssetId && items.length > 1
  const current = items[Math.min(index, items.length - 1)] ?? items[0]
  const [zoom, setZoom] = useState(ZOOM_MIN)
  // A new image starts fitted, so paging never lands you deep inside the previous crop.
  const step = (delta: number) => {
    setSelectedAssetId(items[(index + delta + items.length) % items.length].assetId)
    setZoom(ZOOM_MIN)
  }
  const changeZoom = (delta: number) =>
    setZoom((z) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round((z + delta) * 100) / 100)))
  // At fit the image is bounded by the dialog; zoomed in it grows and the frame scrolls.
  const zoomStyle = zoom === ZOOM_MIN
    ? { maxHeight: '75vh', width: '100%' }
    : { maxHeight: 'none', width: `${zoom * 100}%`, maxWidth: 'none' }

  return <>
    <button type="button" onClick={() => { setSelectedAssetId(assetId); setZoom(ZOOM_MIN); setOpen(true) }} className="block w-full cursor-zoom-in rounded-lg focus-visible:ring-2" aria-label={`Xem lớn: ${title}`}>
      <img src={assetUrl(assetId)} alt={title} loading="lazy" className="aspect-[3/4] w-full rounded-lg bg-muted object-contain" />
    </button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        className="max-h-[95vh] overflow-auto sm:max-w-6xl"
        onKeyDown={(e) => {
          if (canPage && e.key === 'ArrowLeft') step(-1)
          if (canPage && e.key === 'ArrowRight') step(1)
          if (e.key === '+' || e.key === '=') changeZoom(ZOOM_STEP)
          if (e.key === '-') changeZoom(-ZOOM_STEP)
          if (e.key === '0') setZoom(ZOOM_MIN)
        }}
      >
        <DialogTitle>{canPage ? current.title : title}</DialogTitle>
        <DialogDescription>
          {compareAssetId
            ? 'So sánh ảnh nguồn với bản nâng cấp ở kích thước đầy đủ.'
            : canPage
              ? `Ảnh ${index + 1}/${items.length} · dùng ‹ › hoặc mũi tên trái/phải để xem ảnh khác.`
              : 'Ảnh gốc, không phải ảnh cắt từ bảng ảnh.'}
        </DialogDescription>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="icon" aria-label="Thu nhỏ" disabled={zoom <= ZOOM_MIN} onClick={() => changeZoom(-ZOOM_STEP)}>
            <ZoomOutIcon />
          </Button>
          <span role="status" className="min-w-14 text-center text-sm tabular-nums">{Math.round(zoom * 100)}%</span>
          <Button variant="outline" size="icon" aria-label="Phóng to" disabled={zoom >= ZOOM_MAX} onClick={() => changeZoom(ZOOM_STEP)}>
            <ZoomInIcon />
          </Button>
          <Button variant="ghost" size="sm" disabled={zoom === ZOOM_MIN} onClick={() => setZoom(ZOOM_MIN)}>
            <MaximizeIcon /> Vừa khung
          </Button>
          <span className="text-xs text-muted-foreground">Phím + − để phóng to/thu nhỏ, 0 để vừa khung.</span>
        </div>
        <div className={`max-h-[75vh] ${zoom > ZOOM_MIN ? 'overflow-auto' : ''} ${compareAssetId ? 'grid gap-4 md:grid-cols-2' : 'flex items-center gap-2'}`}>
          {compareAssetId && <figure><figcaption>Trước</figcaption><img src={assetUrl(compareAssetId)} alt="Ảnh nguồn trước nâng cấp" style={zoomStyle} className="object-contain" /></figure>}
          {canPage && (
            <Button variant="outline" size="icon" aria-label="Ảnh trước" className="sticky left-0 shrink-0 self-center" onClick={() => step(-1)}>
              <ChevronLeftIcon />
            </Button>
          )}
          <figure className={compareAssetId ? undefined : zoom === ZOOM_MIN ? 'min-w-0 flex-1' : 'shrink-0'}>
            {compareAssetId && <figcaption>Sau</figcaption>}
            <img src={assetUrl(canPage ? current.assetId : assetId)} alt={canPage ? current.title : title} style={zoomStyle} className="mx-auto object-contain" />
          </figure>
          {canPage && (
            <Button variant="outline" size="icon" aria-label="Ảnh sau" className="sticky right-0 shrink-0 self-center" onClick={() => step(1)}>
              <ChevronRightIcon />
            </Button>
          )}
        </div>
        <DownloadLinks assetId={canPage ? current.assetId : assetId} />
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
  const { data: providers } = useProviders()
  const { isFavourite } = useFavouriteModels()
  // Retry can move to another provider; favourites first, then everything usable.
  const choices = (providers ?? [])
    .filter((p) => p.selectable && p.key_configured)
    .flatMap((p) => p.models.map((m) => ({ provider: p.name, id: m.id, label: `${p.display_name} · ${m.display_name}` })))
    .sort((a, b) => Number(isFavourite(b.provider, b.id)) - Number(isFavourite(a.provider, a.id)))
  const [retryOn, setRetryOn] = useState('')
  const retryTarget = choices.find((c) => `${c.provider}/${c.id}` === retryOn)
  return <div className="space-y-2 text-sm">
    <p role="status" className="flex flex-wrap items-center gap-2"><JobStatus job={job} />{active(job) && <span>· Lần thử {job.attempts}/{job.max_attempts}</span>}</p>
    {job.error_message && <p role="alert" className="text-destructive">{job.error_message}</p>}
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-muted-foreground">{job.provider} · {job.model} · {costLabel(job.actual_cost_usd ?? job.estimated_cost_usd)}</span>
      {active(job) && <Button size="sm" variant="outline" disabled={action.isPending || job.cancel_requested} onClick={() => action.mutate({ path: `/jobs/${job.id}/cancel` })}>{job.cancel_requested ? 'Đang huỷ' : 'Huỷ'}</Button>}
      {['failed', 'cancelled'].includes(job.status) && <>
        <select
          aria-label={`Model khi thử lại job ${job.id}`}
          className="rounded border p-1 text-xs"
          value={retryOn}
          onChange={(e) => setRetryOn(e.target.value)}
        >
          <option value="">Giữ {job.model}</option>
          {choices.map((c) => <option key={`${c.provider}/${c.id}`} value={`${c.provider}/${c.id}`}>
            {isFavourite(c.provider, c.id) ? '★ ' : ''}{c.label}
          </option>)}
        </select>
        <Button size="sm" variant="outline" disabled={action.isPending}
          onClick={() => action.mutate({ path: `/jobs/${job.id}/retry`, data: retryTarget ? { provider: retryTarget.provider, model: retryTarget.id } : {} })}>
          {retryTarget ? 'Thử lại với model khác' : 'Thử lại job'}
        </Button>
      </>}
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
