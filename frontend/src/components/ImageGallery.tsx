import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { request, useProjects } from '@/api/client'
import { DownloadLinks, ImagePreview } from '@/components/GenerationUI'
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
  const projects = useProjects()
  const selectedProject = projectId || filterProject
  const params = new URLSearchParams({ offset: String(page * PAGE_SIZE), limit: String(PAGE_SIZE) })
  if (selectedProject) params.set('project_id', selectedProject)
  if (purpose) params.set('purpose', purpose)
  const gallery = useQuery({ queryKey: ['gallery', selectedProject, purpose, page],
    queryFn: () => request<{ total: number; items: GalleryItem[] }>(`/gallery?${params}`), refetchInterval: 10000 })
  const items = gallery.data?.items ?? []
  const title = (item: GalleryItem) => `${item.project_name} · ${PURPOSES[item.purpose] || item.purpose} · ${new Date(item.created_at).toLocaleString('vi-VN')}`
  const images = items.map(item => ({ assetId: item.id, title: title(item) }))

  return <section className="space-y-5" aria-label={projectId ? 'Gallery dự án' : 'Gallery tổng'}>
    <div className="flex flex-wrap items-end gap-4">
      {!projectId && <label className="grid gap-1 text-sm">Dự án
        <select aria-label="Lọc gallery theo dự án" className="rounded border bg-background p-2" value={filterProject} onChange={e => { setFilterProject(e.target.value); setPage(0) }}>
          <option value="">Tất cả dự án</option>
          {projects.data?.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </label>}
      <label className="grid gap-1 text-sm">Loại ảnh
        <select aria-label="Lọc gallery theo loại ảnh" className="rounded border bg-background p-2" value={purpose} onChange={e => { setPurpose(e.target.value); setPage(0) }}>
          <option value="">Tất cả loại ảnh</option>
          {Object.entries(PURPOSES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </label>
      <p className="text-sm text-muted-foreground" role="status">{gallery.data ? `${gallery.data.total} ảnh` : 'Đang tải…'}</p>
    </div>
    <p className="text-sm text-muted-foreground">Ảnh đã tạo thành công từ tất cả đợt và phiên bản, mới nhất trước. Bấm ảnh để xem lớn.</p>
    {gallery.error && <ErrorAlert title="Không tải được gallery" error={gallery.error} />}
    {gallery.isPending && <p>Đang tải ảnh…</p>}
    {gallery.data && !items.length && <p>Chưa có ảnh phù hợp.</p>}
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
      {items.map(item => <article key={item.id} className="min-w-0 space-y-2 rounded-xl border bg-background p-2">
        <ImagePreview assetId={item.id} title={title(item)} gallery={images} />
        <a className="block truncate text-sm font-medium underline" href={`#/projects/${item.project_id}`}>{item.project_name}</a>
        <p className="text-xs">{PURPOSES[item.purpose] || item.purpose}</p>
        <p className="break-words text-xs text-muted-foreground">{item.provider} · {item.model}</p>
        <DownloadLinks assetId={item.id} />
        <details className="text-xs"><summary className="cursor-pointer">Xem prompt</summary><p className="mt-2 whitespace-pre-wrap break-words">{item.prompt}</p></details>
      </article>)}
    </div>
    {!!gallery.data?.total && <div className="flex items-center justify-center gap-4">
      <Button variant="outline" disabled={page === 0 || gallery.isFetching} onClick={() => setPage(p => p - 1)}>Trang trước</Button>
      <span className="text-sm">{page + 1}/{Math.ceil(gallery.data.total / PAGE_SIZE)}</span>
      <Button variant="outline" disabled={(page + 1) * PAGE_SIZE >= gallery.data.total || gallery.isFetching} onClick={() => setPage(p => p + 1)}>Trang sau</Button>
    </div>}
  </section>
}
