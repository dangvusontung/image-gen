import { ImageIcon, PlusIcon, SettingsIcon, Trash2Icon } from 'lucide-react'
import { assetUrl, useDeleteProject, useProjects, type ProjectSummary } from '@/api/client'
import { CreateProjectDialog } from '@/components/CreateProjectDialog'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

const dateFmt = new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' })

export default function Dashboard({
  onOpenProject,
  onOpenSettings,
}: {
  onOpenProject: (id: string) => void
  onOpenSettings: () => void
}) {
  const { data: projects, isPending, error } = useProjects()

  const newButton = (
    <Button size="lg">
      <PlusIcon /> Tạo dự án mới
    </Button>
  )

  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Character Studio</h1>
          <p className="mt-1 text-muted-foreground">Biến ảnh của một người thành nhân vật 3D phong cách hoá, nhất quán.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="lg" onClick={onOpenSettings}>
            <SettingsIcon /> Nhà cung cấp & model
          </Button>
          <CreateProjectDialog trigger={newButton} onCreated={onOpenProject} />
        </div>
      </header>

      {error && <ErrorAlert title="Không tải được danh sách dự án" error={error} />}

      {isPending && (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-64 rounded-xl" />
          ))}
        </div>
      )}

      {projects && projects.length === 0 && (
        <Card className="items-center py-16 text-center">
          <ImageIcon className="size-10 text-muted-foreground" />
          <CardTitle>Chưa có dự án nào</CardTitle>
          <CardDescription>Tạo dự án, tải 3–8 ảnh của cùng một người để bắt đầu.</CardDescription>
          <CreateProjectDialog trigger={<Button>Tạo dự án đầu tiên</Button>} onCreated={onOpenProject} />
        </Card>
      )}

      {projects && projects.length > 0 && (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} onOpen={() => onOpenProject(p.id)} />
          ))}
        </div>
      )}
    </main>
  )
}

function ProjectCard({ project, onOpen }: { project: ProjectSummary; onOpen: () => void }) {
  const remove = useDeleteProject()

  const confirmDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (window.confirm(`Xoá dự án "${project.name}" và toàn bộ ảnh của nó? Không thể hoàn tác.`)) {
      remove.mutate(project.id)
    }
  }

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => e.key === 'Enter' && onOpen()}
      className="cursor-pointer gap-0 overflow-hidden pt-0 transition-shadow hover:shadow-md focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <div className="relative flex aspect-video items-center justify-center overflow-hidden bg-muted">
        {project.thumbnail_asset_id ? (
          <img
            src={assetUrl(project.thumbnail_asset_id)}
            alt=""
            className="absolute inset-0 size-full object-cover"
            loading="lazy"
          />
        ) : (
          <ImageIcon className="size-8 text-muted-foreground" />
        )}
      </div>
      <CardHeader className="pt-4">
        <CardTitle className="truncate">{project.name}</CardTitle>
        {project.description && <CardDescription className="line-clamp-2">{project.description}</CardDescription>}
      </CardHeader>
      <CardContent className="flex items-center justify-between gap-2 pt-3 text-xs text-muted-foreground">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">{project.asset_count} ảnh</Badge>
          {!!project.completed_jobs && <span>{project.completed_jobs} ảnh đã tạo</span>}
          {!!project.active_jobs && <Badge>{project.active_jobs} đang tạo</Badge>}
          {!!project.failed_jobs && <Badge variant="destructive">{project.failed_jobs} lỗi</Badge>}
          <span>Cập nhật {dateFmt.format(new Date(project.updated_at))}</span>
          {project.recent_activity && <span>Gần nhất: {({ master: 'nhân vật gốc', turnaround: 'turnaround', concept: 'concept', enhance: 'nâng cấp' } as Record<string, string>)[project.recent_activity] ?? 'tạo ảnh'}</span>}
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={`Xoá dự án ${project.name}`}
          onClick={confirmDelete}
          disabled={remove.isPending}
        >
          <Trash2Icon />
        </Button>
      </CardContent>
    </Card>
  )
}
