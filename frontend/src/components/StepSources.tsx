import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { assetUrl, request, useReorderAssets, useSetStepLead, useSetStepTemplate, type GenerationJob, type ProjectDetail, type WorkflowStep } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'

export const ANGLE_LABEL: Record<string, string> = {
  front: 'Chính diện 0°', left45: 'Trái 45°', left90: 'Nghiêng trái 90°',
  right45: 'Phải 45°', right90: 'Nghiêng phải 90°', back: 'Sau lưng 180°',
}

export const ANGLE_OPTIONS = Object.entries(ANGLE_LABEL).map(([value, label]) => ({ value, label }))

/** Pin which reference leads this step, instead of letting the app choose automatically. */
export function LeadPicker({ project, step, options }: {
  project: ProjectDetail
  step: WorkflowStep
  options: { value: string; label: string }[]
}) {
  const setLead = useSetStepLead(project.id)
  const current = project.step_leads?.[step] ?? ''
  const stale = current && !(step === 'concept' && current === 'none') && !options.some((o) => o.value === current)

  if (options.length < 2 && step !== 'concept') return null
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <label>
        Ảnh dẫn hướng
        <select
          aria-label={`Ảnh dẫn hướng cho bước ${step}`}
          className="ml-2 rounded border p-2"
          value={stale ? '' : current}
          disabled={setLead.isPending}
          onChange={(e) => setLead.mutate({ step, lead: e.target.value || null })}
        >
          <option value="">Tự động chọn</option>
          {step === 'concept' && <option value="none">Không dùng turnaround</option>}
          {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </label>
      <span className="text-xs text-muted-foreground">
        {current === 'none' && step === 'concept' ? 'Chỉ dùng nhân vật gốc và ảnh mẫu đã chọn.' : current && !stale ? 'Ảnh này được gửi đầu tiên làm mốc nhận diện.' : 'Ứng dụng tự chọn theo góc máy của concept.'}
      </span>
      {setLead.error && <ErrorAlert error={setLead.error} title="Không lưu được ảnh dẫn hướng" />}
    </div>
  )
}

/** Pick the uploaded template image that steers this step's art direction. */
export function TemplatePicker({ project, step }: { project: ProjectDetail; step: WorkflowStep }) {
  const setTemplate = useSetStepTemplate(project.id)
  // Any uploaded photo can steer art direction; ones uploaded as templates list first.
  const rank = (kind: string) => (kind === 'template' ? 0 : 1)
  const choices = [...project.assets].sort((a, b) => rank(a.kind) - rank(b.kind) || a.position - b.position)
  // Empty means the app's own built-in reference, so nothing has to be chosen.
  const current = project.step_templates?.[step] ?? ''

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <label>
        Ảnh mẫu
        <select
          aria-label={`Ảnh mẫu cho bước ${step}`}
          className="ml-2 rounded border p-2"
          value={current}
          disabled={setTemplate.isPending}
          onChange={(e) => setTemplate.mutate({ step, assetId: e.target.value || null })}
        >
          <option value="">Mặc định của ứng dụng</option>
          <option value="none">Không dùng ảnh mẫu</option>
          {choices.map((a) => <option key={a.id} value={a.id}>
            {a.filename}{a.kind === 'template' ? '' : a.kind === 'side_profile' ? ' (ảnh nghiêng)' : ' (ảnh tham chiếu)'}
          </option>)}
        </select>
      </label>
      <span className="text-xs text-muted-foreground">
        {current === 'none'
          ? 'Chỉ dùng prompt để định hướng phong cách.'
          : 'Chỉ lấy chất liệu, bố cục, ánh sáng từ ảnh mẫu — không lấy khuôn mặt hay trang phục.'}
      </span>
      {setTemplate.error && <ErrorAlert error={setTemplate.error} title="Không lưu được ảnh mẫu" />}
    </div>
  )
}

export function SourceImages({ images, onBack, lead, onReorder }: {
  images: { id: string; label: string }[]
  onBack?: () => void
  lead?: React.ReactNode
  /** Supplied when these images are the project's own photos and can be reordered here. */
  onReorder?: (orderedIds: string[]) => void
}) {
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [overIndex, setOverIndex] = useState<number | null>(null)

  const drop = (index: number) => {
    if (onReorder && dragIndex !== null && dragIndex !== index) {
      const ids = images.map((i) => i.id)
      const [moved] = ids.splice(dragIndex, 1)
      ids.splice(index, 0, moved)
      onReorder(ids)
    }
    setDragIndex(null)
    setOverIndex(null)
  }

  return <section aria-label="Ảnh đã chọn từ bước trước" className="mb-5 space-y-3 rounded-xl border bg-muted/30 p-4">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">Ảnh đã chọn từ bước trước</h2>
      {onBack && <Button size="sm" variant="outline" onClick={onBack}>Quay lại đổi lựa chọn</Button>}
    </div>
    {lead}
    {!images.length && <p className="text-sm text-muted-foreground">Chưa có ảnh đã chọn. Hoàn thành bước trước để tiếp tục.</p>}
    {onReorder && images.length > 1 && <p className="text-xs text-muted-foreground">
      Kéo thả để đổi thứ tự. Ảnh đầu tiên ảnh hưởng nhiều nhất tới trang phục và bố cục.
    </p>}
    <div className="flex flex-wrap gap-3">{images.map((image, index) => <figure
      key={`${image.id}/${index}`}
      draggable={Boolean(onReorder)}
      onDragStart={onReorder ? (e) => { e.dataTransfer.effectAllowed = 'move'; setDragIndex(index) } : undefined}
      onDragEnter={onReorder ? () => setOverIndex(index) : undefined}
      onDragOver={onReorder ? (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move' } : undefined}
      onDragEnd={onReorder ? () => { setDragIndex(null); setOverIndex(null) } : undefined}
      onDrop={onReorder ? (e) => { e.preventDefault(); drop(index) } : undefined}
      className={`w-24 space-y-1 rounded-lg ${onReorder ? 'cursor-grab active:cursor-grabbing' : ''} ${
        dragIndex === index ? 'opacity-40' : ''} ${
        overIndex === index && dragIndex !== null && dragIndex !== index ? 'ring-2 ring-primary' : ''}`}
    >
      <div className="relative">
        <img data-source-image src={assetUrl(image.id)} alt={image.label} className="aspect-[3/4] w-full rounded-lg border bg-muted object-contain" />
        {onReorder && <span className="absolute top-1 left-1 rounded bg-background/90 px-1 text-xs">#{index + 1}</span>}
      </div>
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
  // Deselected photos are never sent, so they are not shown as sources either.
  const used = project.assets.filter(a => a.selected)
  const images = step === 'master' ? used.map(a => ({ id: a.id, label: `${a.kind === 'side_profile' ? 'Ảnh nghiêng' : 'Ảnh tham chiếu'} · ${a.filename}` })) : [
    ...(master?.job.output_asset_ids[0] ? [{ id: master.job.output_asset_ids[0], label: `Master đã duyệt · Lần ${master.round}, bản ${master.variant}` }] : []),
    ...(step === 'turnaround' ? used.filter(a => a.kind === 'side_profile').map(a => ({ id: a.id, label: `Ảnh nghiêng · ${a.filename}` })) : project.step_leads?.concept === 'none' ? [] : turn?.views.filter(v => v.job.status === 'succeeded' && v.job.output_asset_ids[0]).map(v => ({ id: v.job.output_asset_ids[0], label: `Turnaround ${turn.number} · ${v.angle}` })) ?? []),
  ]
  const angles = (turn?.views ?? [])
    .filter(v => v.job.status === 'succeeded' && v.job.output_asset_ids[0])
    .map(v => ({ value: v.angle, label: ANGLE_LABEL[v.angle] ?? v.angle }))
  const leadOptions: Record<typeof step, { value: string; label: string }[]> = {
    // Step 2 leads with one of the uploaded photos; step 3 with one of the side profiles.
    master: used.map(a => ({ value: a.id, label: a.filename })),
    turnaround: used.filter(a => a.kind === 'side_profile').map(a => ({ value: a.id, label: a.filename })),
    concepts: angles,
  }
  const leadStep: WorkflowStep = step === 'concepts' ? 'concept' : step

  // Only the master step shows the project's own photos, so only there can order be changed.
  const reorder = useReorderAssets(project.id)
  const reorderUsed = (orderedIds: string[]) => {
    const all = [...project.assets].sort((a, b) => a.position - b.position).map((a) => a.id)
    const slots = all.map((id, i) => (orderedIds.includes(id) ? i : -1)).filter((i) => i >= 0)
    const next = [...all]
    // Drop the new sequence into the slots the shown photos already occupy, leaving the rest put.
    slots.forEach((slot, i) => { next[slot] = orderedIds[i] })
    reorder.mutate(next)
  }

  return <>
    {workflow.error && <ErrorAlert error={workflow.error} title="Không tải được lựa chọn trước" />}
    {reorder.error && <ErrorAlert error={reorder.error} title="Không đổi được thứ tự ảnh" />}
    <SourceImages
      images={images}
      onBack={onBack}
      onReorder={step === 'master' && used.length > 1 ? reorderUsed : undefined}
      lead={<>
        <LeadPicker project={project} step={leadStep} options={leadOptions[step]} />
        <TemplatePicker project={project} step={leadStep} />
      </>}
    />
  </>
}
