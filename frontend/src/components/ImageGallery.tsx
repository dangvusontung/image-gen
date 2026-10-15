import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { assetUrl, request, useProjects } from '@/api/client'
import { DownloadLinks } from '@/components/GenerationUI'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'

const PURPOSES: Record<string, string> = { master: 'Nhân vật gốc', turnaround: 'Turnaround', concept: 'Concept', enhance: 'Nâng cấp', test: 'Ảnh thử' }
interface GalleryItem {
  id: string; project_id: string; project_name: string; purpose: string
  provider: string; model: string; prompt: string; created_at: string
}
const PAGE_SIZE = 48

export default function ImageGallery({ projectId }: { projectId?: string }) {
  const [filterProject, setFilterProject] = useState('')
  const [purpose, setPurpose] = useState('')
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<string[]>([])
  const [detail, setDetail] = useState<GalleryItem | null>(null)
  const download = useMutation({ mutationFn: async () => {
    const blob = await request<Blob>('/gallery/download', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ asset_ids: selected }) }, 'blob')
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'gallery-selected.zip'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } })
  const projects = useProjects()
  const selectedProject = projectId || filterProject
  const params = new URLSearchParams({ offset: String(page * PAGE_SIZE), limit: String(PAGE_SIZE) })
  if (selectedProject) params.set('project_id', selectedProject)
  if (purpose) params.set('purpose', purpose)
  const gallery = useQuery({ queryKey: ['gallery', selectedProject, purpose, page],
    queryFn: () => request<{ total: number; items: GalleryItem[] }>(`/gallery?${params}`), refetchInterval: 10000 })
  const items = gallery.data?.items ?? []
  const title = (item: GalleryItem) => `${item.project_name} · ${PURPOSES[item.purpose] || item.purpose} · ${new Date(item.created_at).toLocaleString('vi-VN')}`
  const [navigating, setNavigating] = useState(false)
  const detailIndex = detail ? items.findIndex(item => item.id === detail.id) : -1
  const hasPrevious = detailIndex > 0 || page > 0
  const hasNext = detailIndex >= 0 && (detailIndex < items.length - 1 || (page + 1) * PAGE_SIZE < (gallery.data?.total ?? 0))
  const moveDetail = async (direction: number) => {
    if (navigating || !detail || detailIndex < 0) return
    const next = detailIndex + direction
    if (items[next]) { setDetail(items[next]); return }
    const nextPage = page + direction
    if (nextPage < 0 || nextPage * PAGE_SIZE >= (gallery.data?.total ?? 0)) return
    setNavigating(true)
    try {
      const nextParams = new URLSearchParams(params)
      nextParams.set('offset', String(nextPage * PAGE_SIZE))
      const result = await request<{ total: number; items: GalleryItem[] }>(`/gallery?${nextParams}`)
      const target = direction > 0 ? result.items[0] : result.items[result.items.length - 1]
      if (target) { setPage(nextPage); setDetail(target) }
    } finally { setNavigating(false) }
  }
  const [navigationError, setNavigationError] = useState<unknown>(null)
  const navigateDetail = (direction: number) => { setNavigationError(null); void moveDetail(direction).catch(setNavigationError) }
  useEffect(() => {
    if (!detail) return
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault()
        navigateDetail(event.key === 'ArrowLeft' ? -1 : 1)
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  })
  const allPageSelected = items.length > 0 && items.every(item => selected.includes(item.id))

  return <section className="space-y-5" aria-label={projectId ? 'Gallery dự án' : 'Gallery tổng'}>
    <div className="flex flex-wrap items-end gap-4">
      {!projectId && <label className="grid gap-1 text-sm">Dự án
        <select aria-label="Lọc gallery theo dự án" className="rounded border bg-background p-2" value={filterProject} onChange={e => { setFilterProject(e.target.value); setPage(0); setSelected([]) }}>
          <option value="">Tất cả dự án</option>
          {projects.data?.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </label>}
      <label className="grid gap-1 text-sm">Loại ảnh
        <select aria-label="Lọc gallery theo loại ảnh" className="rounded border bg-background p-2" value={purpose} onChange={e => { setPurpose(e.target.value); setPage(0); setSelected([]) }}>
          <option value="">Tất cả loại ảnh</option>
          {Object.entries(PURPOSES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </label>
      <p className="text-sm text-muted-foreground" role="status">{gallery.data ? `${gallery.data.total} ảnh` : 'Đang tải…'}</p>
    </div>
    <p className="text-sm text-muted-foreground">Ảnh đã tạo thành công từ tất cả đợt và phiên bản, mới nhất trước. Bấm ảnh để xem chi tiết. Chọn ảnh ở nhiều trang để tải chung một ZIP (tối đa 500 ảnh).</p>
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="outline" disabled={!items.length || download.isPending} onClick={() => setSelected(current => allPageSelected ? current.filter(id => !items.some(item => item.id === id)) : [...new Set([...current, ...items.map(item => item.id)])].slice(0, 500))}>{allPageSelected ? 'Bỏ chọn trang này' : 'Chọn trang này'}</Button>
      <Button variant="outline" disabled={!selected.length || download.isPending} onClick={() => setSelected([])}>Bỏ chọn tất cả</Button>
      <Button disabled={!selected.length || download.isPending} onClick={() => download.mutate()}>{download.isPending ? 'Đang chuẩn bị ZIP…' : `Tải ${selected.length} ảnh đã chọn (ZIP)`}</Button>
    </div>
    {download.error && <ErrorAlert title="Không tải được ảnh" error={download.error} />}
    {gallery.error && <ErrorAlert title="Không tải được gallery" error={gallery.error} />}
    {gallery.isPending && <p>Đang tải ảnh…</p>}
    {gallery.data && !items.length && <p>Chưa có ảnh phù hợp.</p>}
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
      {items.map(item => <article key={item.id} className={`relative min-w-0 overflow-hidden rounded-lg ${selected.includes(item.id) ? 'ring-2 ring-primary' : ''}`}>
        <button type="button" className="block w-full cursor-zoom-in focus-visible:ring-2" aria-label={`Xem chi tiết: ${title(item)}`} onClick={() => setDetail(item)}>
          <img src={assetUrl(item.id)} alt={title(item)} loading="lazy" className="aspect-[3/4] w-full bg-muted object-contain" />
        </button>
        <label className="absolute left-2 top-2 flex cursor-pointer rounded bg-background/90 p-2">
          <input type="checkbox" aria-label={`Chọn ảnh ${item.id}`} checked={selected.includes(item.id)} disabled={download.isPending || (!selected.includes(item.id) && selected.length >= 500)} onChange={e => setSelected(current => e.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))} />
        </label>
      </article>)}
    </div>
    <Dialog open={Boolean(detail)} onOpenChange={open => { if (!open) { setDetail(null); setNavigationError(null) } }}>
      <DialogContent className="!flex h-[90dvh] !w-[96vw] !max-w-[1440px] flex-col gap-0 overflow-hidden p-0">
        {detail && <>
          <DialogTitle className="sr-only">{detail.project_name} · {PURPOSES[detail.purpose] || detail.purpose}</DialogTitle>
          <DialogDescription className="sr-only">Xem ảnh và thông tin chi tiết. Dùng nút hoặc phím mũi tên trái phải để chuyển ảnh.</DialogDescription>
          <div className="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)_minmax(0,35%)] md:grid-cols-[minmax(0,1fr)_20rem] md:grid-rows-1">
            <div className="relative flex min-h-0 min-w-0 items-center justify-center bg-black">
              <img src={assetUrl(detail.id)} alt={title(detail)} className="h-full w-full object-contain" />
              <Button variant="ghost" size="icon" aria-label="Ảnh trước" className="absolute left-3 top-1/2 size-11 -translate-y-1/2 rounded-full bg-black/50 text-3xl text-white hover:bg-black/80 hover:text-white" disabled={!hasPrevious || navigating || gallery.isFetching} onClick={() => navigateDetail(-1)}>‹</Button>
              <Button variant="ghost" size="icon" aria-label="Ảnh sau" className="absolute right-3 top-1/2 size-11 -translate-y-1/2 rounded-full bg-black/50 text-3xl text-white hover:bg-black/80 hover:text-white" disabled={!hasNext || navigating || gallery.isFetching} onClick={() => navigateDetail(1)}>›</Button>
            </div>
            <div className="min-h-0 min-w-0 space-y-4 overflow-y-auto p-5 pt-10">
              <a className="block text-lg font-semibold underline" href={`#/projects/${detail.project_id}`}>{detail.project_name}</a>
              <p className="text-sm">{PURPOSES[detail.purpose] || detail.purpose}</p>
              <p className="text-xs text-muted-foreground">{new Date(detail.created_at).toLocaleString('vi-VN')}</p>
              <p className="break-words text-sm">{detail.provider} · {detail.model}</p>
              <DownloadLinks assetId={detail.id} />
              <h3 className="font-medium">Prompt</h3>
              <p className="whitespace-pre-wrap break-words text-sm">{detail.prompt}</p>
              {navigationError != null && <ErrorAlert title="Không chuyển được ảnh" error={navigationError} />}
            </div>
          </div>
        </>}
      </DialogContent>
    </Dialog>
    {!!gallery.data?.total && <div className="flex items-center justify-center gap-4">
      <Button variant="outline" disabled={page === 0 || gallery.isFetching} onClick={() => setPage(p => p - 1)}>Trang trước</Button>
      <span className="text-sm">{page + 1}/{Math.ceil(gallery.data.total / PAGE_SIZE)}</span>
      <Button variant="outline" disabled={(page + 1) * PAGE_SIZE >= gallery.data.total || gallery.isFetching} onClick={() => setPage(p => p + 1)}>Trang sau</Button>
    </div>}
  </section>
}
