import { ConceptMenu, useConceptChoices } from '@/components/ConceptMenu'
import { defaultGenerationSize } from '@/lib/generationPolicy'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { request, useProviders, type Concept, type ProjectDetail } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { active, costLabel, DownloadLinks, ImagePreview, JobDetails, JobPlaceholder, PromptEditor, useGenerationAction } from '@/components/GenerationUI'

export default function ConceptsStep({ project, onEnhance }: { project: ProjectDetail; onEnhance: (id: string) => void }) {
  const [batch, setBatch] = useState<'A' | 'B'>('A')
  const [selectedRun, setSelectedRun] = useState<number | null>(null)
  const [sheet, setSheet] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [size, setSize] = useState('')
  const [count, setCount] = useState(5)
  const [choices, setChoices] = useConceptChoices(project.id)
  const base = `/projects/${project.id}`
  const concepts = useQuery({ queryKey: ['concepts', project.id], queryFn: () => request<Concept[]>(`${base}/concepts`), refetchInterval: 1500 })
  const workflow = useQuery({ queryKey: ['workflow', project.id], queryFn: () => request<{ approved_master_id: string | null }>(`${base}/workflow`), refetchInterval: 1500 })
  const providers = useProviders()
  const model = providers.data?.find(p => p.name === project.provider)?.models.find(m => m.id === project.model)
  const action = useGenerationAction(project.id)
  const runs = [...new Set(concepts.data?.filter(c => c.batch === batch).map(c => c.run) ?? [])].sort((a, b) => b - a)
  const run = selectedRun ?? runs[0]
  const all = concepts.data?.filter(c => c.batch === batch && c.run === run) ?? []
  const slots = batch === 'A' ? [1, 2, 3, 4, 5] : [6, 7, 8, 9]
  const cards = slots.map(slot => all.filter(c => c.slot === slot).sort((a, b) => b.revision - a.revision)[0]).filter(Boolean)
  const paid = project.provider !== 'mock'
  const resolvedSize = size || defaultGenerationSize(project, model?.default_size)
  const unitPrice = (resolvedSize ? model?.price_table?.[resolvedSize] : undefined) ?? model?.price_per_image_usd
  const pending = action.isPending
  const ready = project.rights_confirmed && Boolean(workflow.data?.approved_master_id)
  const estimate = useQuery({ queryKey: ['estimate', project.id, project.provider, project.model, size, batch, count], enabled: ready,
    queryFn: () => request<{ total_usd: number | null; note: string }>(`${base}/generation-estimate?purpose=concept&count=${count}${size ? `&size=${encodeURIComponent(size)}` : ''}`), refetchInterval: 3000 })
  const generate = () => action.mutate({ path: `${base}/concepts/generate`, data: { batch, confirmed, count, choices, size: size || null } }, { onSuccess: () => setSelectedRun(null) })

  return <section className="space-y-5">
    <h2 className="text-xl font-semibold">Concept tùy chọn</h2>
    <p className="text-sm text-muted-foreground">Mỗi ô là một ảnh đầy đủ. Các bối cảnh và hoạt động được thay đổi giữa các đợt; nhân vật gốc giữ vai trò nhận diện chính.</p>
    <ConceptMenu projectId={project.id} choices={choices} onChange={value => { setChoices(value); setConfirmed(false) }} />
    <PromptEditor projectId={project.id} name="concept" />
    <div className="flex flex-wrap gap-2" role="group" aria-label="Chọn batch">
      {(['A', 'B'] as const).map(b => <Button key={b} variant={batch === b ? 'default' : 'outline'} onClick={() => { setBatch(b); setCount(b === 'A' ? 5 : 4); setSelectedRun(null); setConfirmed(false) }}>Batch {b} · {b === 'A' ? 5 : 4} ảnh</Button>)}
    </div>
    <div className="flex flex-wrap items-center gap-4 rounded-lg border p-4">
      <label className="text-sm">Số ảnh <select aria-label="Số ảnh concept" className="ml-2 rounded border p-2" value={count} onChange={e => { setCount(Number(e.target.value)); setConfirmed(false) }}>{slots.map((_, i) => <option key={i + 1}>{i + 1}</option>)}</select></label>
      {!!model?.sizes?.length && <label className="text-sm">Kích thước <select aria-label="Kích thước concept" className="ml-2 rounded border p-2" value={size} onChange={e => { setSize(e.target.value); setConfirmed(false) }}>
        <option value="">Mặc định ({defaultGenerationSize(project, model.default_size)})</option>{model.sizes.map(s => <option key={s}>{s}</option>)}
      </select></label>}
      <p className="text-sm">{costLabel(estimate.data ? estimate.data.total_usd : unitPrice == null ? null : unitPrice * count)} / {count} ảnh</p>
      {paid && <label className="text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> Xác nhận chi phí batch {batch} và gửi ảnh tới nhà cung cấp</label>}
      <Button disabled={pending || !ready || (paid && !confirmed) || (choices.outfit === 'custom' && !choices.custom_outfit.trim()) || (choices.scene === 'custom' && !choices.custom_scene.trim())} onClick={generate}>Tạo batch {batch}</Button>
      {!ready && <p className="text-sm">Xác nhận quyền sử dụng ảnh và duyệt nhân vật gốc để tiếp tục.</p>}
    </div>
    {estimate.data && <p className="text-xs text-muted-foreground">{estimate.data.note}</p>}
    {action.error && <ErrorAlert error={action.error} title="Không tạo được ảnh" />}
    {concepts.error && <ErrorAlert error={concepts.error} title="Không tải được concept" />}
    {workflow.error && <ErrorAlert error={workflow.error} title="Không tải được nhân vật gốc" />}
    {concepts.isPending && <Skeleton className="h-64" />}
    {!!runs.length && <div className="flex flex-wrap items-center gap-4">
      <label>Đợt <select className="ml-2 rounded border p-2" aria-label="Đợt concept" value={run} onChange={e => setSelectedRun(Number(e.target.value))}>
        {runs.map(n => <option key={n} value={n}>{n}</option>)}
      </select></label>
      <Button variant="outline" onClick={() => setSheet(!sheet)}>{sheet ? 'Xem thẻ chi tiết' : 'Xem bảng ảnh'}</Button>
      <a className="text-sm underline" href={`/api${base}/contact-sheet?batch=${batch}&run=${run}`}>Tải bảng ảnh batch {batch}</a>
      <span className="text-sm">{cards.filter(c => c?.job.status === 'succeeded').length}/{cards.length} hoàn tất</span>
    </div>}
    {!concepts.isPending && !runs.length && <p className="rounded-lg bg-muted p-8 text-center">Chưa có concept batch {batch}. Tạo batch để bắt đầu.</p>}
    {!!runs.length && <div className={`grid gap-4 ${sheet ? 'grid-cols-2 md:grid-cols-3 lg:grid-cols-5' : 'sm:grid-cols-2 lg:grid-cols-3'}`}>
      {cards.map((c, index) => c ? <article key={c.id} className="space-y-3 rounded-xl border p-4" aria-label={`Concept ${c.batch}${c.slot}`}>
        <h3 className="font-semibold">{c.batch}{c.slot} · {c.mood}</h3>
        <p className="text-sm text-muted-foreground">{c.camera} · Bản {c.revision}</p>
        {c.stale && <p className="text-sm text-amber-700">Dựa trên nhân vật gốc cũ</p>}
        {c.job.output_asset_ids[0] ? <><ImagePreview assetId={c.job.output_asset_ids[0]} title={`Concept ${c.batch}${c.slot} · ${c.mood}`} /><DownloadLinks assetId={c.job.output_asset_ids[0]} /></> : active(c.job) ? <JobPlaceholder job={c.job} /> : <div className="flex aspect-[3/4] items-center justify-center rounded-lg bg-muted text-sm">Chưa có ảnh kết quả</div>}
        {!sheet && <>
          <p className="text-sm">Trang phục: {c.brief.outfit}</p>
          <p className="text-sm">{c.brief.setting} · {c.brief.activity}</p>
          <details className="text-xs"><summary>Chi tiết concept và phiên bản trước</summary>
            <dl className="mt-2 space-y-1">{Object.entries(c.brief).map(([k, v]) => <div key={k}><dt className="inline font-medium">{({ setting: 'Bối cảnh', activity: 'Hoạt động', outfit: 'Trang phục', pose: 'Tư thế', expression: 'Biểu cảm', gaze: 'Hướng nhìn', camera: 'Máy ảnh', lighting: 'Ánh sáng' } as Record<string, string>)[k]}: </dt><dd className="inline">{v}</dd></div>)}</dl>
            {all.filter(p => p.slot === c.slot && p.id !== c.id).map(p => <div key={p.id} className="mt-3 border-t pt-3"><p>Bản {p.revision}</p>{p.job.output_asset_ids[0] && <><ImagePreview assetId={p.job.output_asset_ids[0]} title={`Concept ${p.batch}${p.slot} bản ${p.revision}`} /><Button size="sm" variant="outline" onClick={() => onEnhance(p.id)}>Nâng cấp bản {p.revision}</Button></>}<JobDetails job={p.job} projectId={project.id} /></div>)}
          </details>
          <JobDetails job={c.job} projectId={project.id} />
        </>}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={pending || active(c.job) || !ready} onClick={() => action.mutate({ path: `${base}/concepts/${c.id}/regenerate`, data: { size: size || null, choices } })}>Tạo lại ô {c.slot}</Button>
          <Button size="sm" disabled={c.job.status !== 'succeeded'} onClick={() => onEnhance(c.id)}>Nâng cấp ô {c.slot}</Button>
        </div>
      </article> : <div key={index} className="rounded-xl border bg-muted p-8">Ô {slots[index]} · Chưa có ảnh</div>)}
    </div>}
  </section>
}
