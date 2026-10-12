import { ChevronRightIcon, FolderIcon, LoaderCircleIcon } from 'lucide-react'
import { useState } from 'react'
import { useProjects } from '@/api/client'

/** Right-edge rail for hopping between projects without going back to the dashboard. */
export default function ProjectSwitcher({ projectId, onOpen }: { projectId: string; onOpen: (id: string) => void }) {
  const [open, setOpen] = useState(false)
  const { data: projects } = useProjects()

  if (!projects?.length) return null
  const busy = projects.filter((p) => p.active_jobs > 0)
  return (
    <aside
      aria-label="Chuyển dự án"
      className={`fixed top-1/2 right-0 z-40 -translate-y-1/2 rounded-l-xl border border-r-0 bg-popover shadow-lg ${open ? 'w-60' : ''}`}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-label={open ? 'Thu gọn danh sách dự án'
          : busy.length ? `Mở danh sách dự án · ${busy.length} dự án đang tạo ảnh` : 'Mở danh sách dự án'}
        className="flex w-full items-center gap-2 p-2 text-sm"
        onClick={() => setOpen(!open)}
      >
        <ChevronRightIcon className={`size-4 shrink-0 transition-transform ${open ? '' : 'rotate-180'}`} aria-hidden />
        {open
          ? <span className="font-medium">Dự án</span>
          : busy.length
            ? <LoaderCircleIcon className="size-4 animate-spin text-amber-600" aria-hidden />
            : <FolderIcon className="size-4" aria-hidden />}
        {!open && busy.length > 0 && <span className="text-xs font-medium text-amber-700">{busy.length}</span>}
      </button>
      {open && <ul className="max-h-[60vh] space-y-1 overflow-auto border-t p-2">
        {[...projects].sort((a, b) => Number(b.active_jobs > 0) - Number(a.active_jobs > 0)).map((p) => (
          <li key={p.id}>
            <button
              type="button"
              className={`w-full truncate rounded px-2 py-1.5 text-left text-sm ${
                p.id === projectId ? 'bg-muted font-medium' : 'hover:bg-muted'}`}
              aria-current={p.id === projectId ? 'true' : undefined}
              onClick={() => { onOpen(p.id); setOpen(false) }}
            >
              <span className="flex items-center gap-1.5">
                {p.active_jobs > 0 && <LoaderCircleIcon className="size-3.5 shrink-0 animate-spin text-amber-600" aria-hidden />}
                <span className="truncate">{p.name}</span>
              </span>
              <span className="block truncate text-xs text-muted-foreground">
                {p.active_jobs > 0 && <span className="text-amber-700">{p.active_jobs} đang tạo · </span>}
                {p.failed_jobs > 0 && <span className="text-destructive">{p.failed_jobs} lỗi · </span>}
                {p.asset_count} ảnh · {p.completed_jobs} ảnh đã tạo
              </span>
            </button>
          </li>
        ))}
      </ul>}
    </aside>
  )
}
