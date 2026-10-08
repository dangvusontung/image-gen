import { useQuery } from '@tanstack/react-query'
import { assetUrl, request, type GenerationJob, type ProjectDetail } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'

export function SourceImages({ images, onBack }: { images: { id: string; label: string }[]; onBack?: () => void }) {
  return <section aria-label="Ảnh đã chọn từ bước trước" className="mb-5 space-y-3 rounded-xl border bg-muted/30 p-4">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">Ảnh đã chọn từ bước trước</h2>
      {onBack && <Button size="sm" variant="outline" onClick={onBack}>Quay lại đổi lựa chọn</Button>}
    </div>
    {!images.length && <p className="text-sm text-muted-foreground">Chưa có ảnh đã chọn. Hoàn thành bước trước để tiếp tục.</p>}
    <div className="flex flex-wrap gap-3">{images.map((image, index) => <figure key={`${image.id}/${index}`} className="w-24 space-y-1">
      <a href={assetUrl(image.id)} target="_blank" rel="noreferrer" aria-label={`Xem ảnh nguồn: ${image.label}`}>
        <img data-source-image src={assetUrl(image.id)} alt={image.label} className="aspect-[3/4] w-full rounded-lg border bg-muted object-contain" />
      </a>
      <figcaption className="break-words text-xs text-muted-foreground">{image.label}</figcaption>
    </figure>)}</div>
  </section>
}

interface Workflow {
  approved_master_id: string | null; approved_turnaround_id: string | null
  masters: { id: string; round: number; variant: number; job: GenerationJob }[]
  turnarounds: { id: string; number: number; master_version_id: string; views: { angle: string; job: GenerationJob }[] }[]
}

export default function StepSources({ project, step, onBack }: { project: ProjectDetail; step: 'master' | 'turnaround' | 'concepts'; onBack: () => void }) {
  const workflow = useQuery({ queryKey: ['workflow', project.id], enabled: step !== 'master', queryFn: () => request<Workflow>(`/projects/${project.id}/workflow`), refetchInterval: 1500 })
  const data = workflow.data
  const master = data?.masters.find(m => m.id === data.approved_master_id)
  const turn = data?.turnarounds.find(t => t.id === data.approved_turnaround_id && t.master_version_id === master?.id)
  const images = step === 'master' ? project.assets.map(a => ({ id: a.id, label: `${a.kind === 'side_profile' ? 'Ảnh nghiêng' : 'Ảnh tham chiếu'} · ${a.filename}` })) : [
    ...(master?.job.output_asset_ids[0] ? [{ id: master.job.output_asset_ids[0], label: `Master đã duyệt · Lần ${master.round}, bản ${master.variant}` }] : []),
    ...(step === 'turnaround' ? project.assets.filter(a => a.kind === 'side_profile').map(a => ({ id: a.id, label: `Ảnh nghiêng · ${a.filename}` })) : turn?.views.filter(v => v.job.status === 'succeeded' && v.job.output_asset_ids[0]).map(v => ({ id: v.job.output_asset_ids[0], label: `Turnaround ${turn.number} · ${v.angle}` })) ?? []),
  ]
  return <>{workflow.error && <ErrorAlert error={workflow.error} title="Không tải được lựa chọn trước" />}<SourceImages images={images} onBack={onBack} /></>
}
