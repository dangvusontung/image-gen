import { SourceImages } from '@/components/StepSources'
import { defaultGenerationSize } from '@/lib/generationPolicy'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { request, useProviders, type Concept, type Enhancement, type ProjectDetail, type ReferencePlan } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'
import { active, costLabel, DownloadLinks, ImagePreview, JobDetails, JobPlaceholder, PromptEditor, useGenerationAction } from '@/components/GenerationUI'

export default function EnhanceStep({ project, selectedConceptId, onSelect, onBack }: { project: ProjectDetail; selectedConceptId: string | null; onSelect: (id: string) => void; onBack?: () => void }) {
  const base = `/projects/${project.id}`
  const [size, setSize] = useState('')
  const [confirmedPlan, setConfirmedPlan] = useState<string | null>(null)
  const concepts = useQuery({ queryKey: ['concepts', project.id], queryFn: () => request<Concept[]>(`${base}/concepts`), refetchInterval: 1500 })
  const versions = useQuery({ queryKey: ['enhancements', project.id], queryFn: () => request<Enhancement[]>(`${base}/enhancements`), refetchInterval: 1500 })
  const successful = concepts.data?.filter(c => c.job.status === 'succeeded') ?? []
  const selected = successful.find(c => c.id === selectedConceptId)
    ?? successful.find(c => c.id === versions.data?.[0]?.concept_id)
    ?? successful[0]
  const planPath = `${base}/concepts/${selected?.id}/enhance-plan${size ? `?size=${encodeURIComponent(size)}` : ''}`
  const plan = useQuery({ queryKey: ['enhance-plan', project.id, selected?.id, project.provider, project.model, size],
    enabled: Boolean(selected), queryFn: () => request<ReferencePlan>(planPath), refetchInterval: 3000 })
  const providers = useProviders()
  const model = providers.data?.find(p => p.name === project.provider)?.models.find(m => m.id === project.model)
  const action = useGenerationAction(project.id)
  const signature = JSON.stringify([selected?.id, project.provider, project.model, size, plan.data?.reference_asset_ids, plan.data?.omitted_asset_ids])
  const confirmed = confirmedPlan === signature
  const history = versions.data?.filter(v => v.concept_id === selected?.id) ?? []

  return <section className="space-y-5">
    <h2 className="text-xl font-semibold">Nâng cấp một concept</h2>
    <p className="text-sm text-muted-foreground">Tạo lại một ảnh 3:4 độc lập, giữ cảnh, trang phục, tư thế, biểu cảm và góc máy. Nhân vật gốc đã duyệt là nguồn nhận diện chính.</p>
    <PromptEditor projectId={project.id} name="enhance" />
    {concepts.error && <ErrorAlert error={concepts.error} title="Không tải được concept" />}
    {versions.error && <ErrorAlert error={versions.error} title="Không tải được bản nâng cấp" />}
    {!concepts.isPending && !successful.length && <p className="rounded-lg bg-muted p-8 text-center">Tạo thành công ít nhất một concept ở bước 4 để nâng cấp.</p>}
    {selected && <>
      {plan.data && <SourceImages onBack={onBack} images={plan.data.reference_asset_ids.map((id, index) => ({ id, label: plan.data.reference_labels[index] ?? 'Ảnh tham chiếu' }))} />}
      <label className="block text-sm">Concept nguồn <select aria-label="Concept nguồn" className="mt-2 block w-full rounded border p-2" value={selected.id} onChange={e => onSelect(e.target.value)}>
        {successful.map(c => <option key={c.id} value={c.id}>{c.batch}{c.slot} · {c.mood} · Đợt {c.run}, bản {c.revision}{c.stale ? ' (master cũ)' : ''}</option>)}
      </select></label>
      {selected.stale && <p className="text-sm text-amber-700">Concept nguồn dùng master cũ. Bản nâng cấp sẽ giữ cảnh và dùng nhân vật gốc đã duyệt hiện tại.</p>}
      <div className="flex flex-wrap items-center gap-4 rounded-lg border p-4">
        {!!model?.sizes?.length && <label className="text-sm">Kích thước <select aria-label="Kích thước nâng cấp" className="ml-2 rounded border p-2" value={size} onChange={e => setSize(e.target.value)}><option value="">Mặc định ({defaultGenerationSize(project, model.default_size)})</option>{model.sizes.map(s => <option key={s}>{s}</option>)}</select></label>}
        <span className="text-sm">{model?.display_name} · {costLabel(plan.data?.estimated_cost_usd)} / ảnh · 3:4</span>
        <Button disabled={action.isPending || !plan.data || plan.isError || !project.rights_confirmed || Boolean(plan.data.warning && !confirmed) || history.some(v => active(v.job))}
          onClick={() => action.mutate({ path: `${base}/concepts/${selected.id}/enhance`, data: { size: size || null, confirm_reference_subset: confirmed } })}>Nâng cấp concept đã chọn</Button>
      </div>
      {project.provider !== 'mock' && <p className="text-sm">Master, concept và ảnh turnaround sẽ được gửi tới nhà cung cấp đã chọn.</p>}
      {project.provider === 'gemini' && <p className="text-xs text-muted-foreground">Ước tính ảnh đầu ra chưa gồm token đầu vào/văn bản.</p>}
      {plan.error && <ErrorAlert error={plan.error} title="Không chuẩn bị được tham chiếu" />}
      {plan.data && <div className="rounded-lg bg-muted p-4 text-sm">
        <p>{plan.data.reference_asset_ids.length} ảnh tham chiếu: {plan.data.reference_labels.join(' · ')}</p>
        {plan.data.warning && <><p role="alert" className="mt-2 text-amber-700">{plan.data.warning}</p>
          <label className="mt-2 block"><input type="checkbox" checked={confirmed} onChange={e => setConfirmedPlan(e.target.checked ? signature : null)} /> Tôi đồng ý dùng tập tham chiếu đã hiển thị</label></>}
      </div>}
      {action.error && <ErrorAlert error={action.error} title="Không nâng cấp được" />}
      <div className="grid gap-6 lg:grid-cols-2">
        <figure className="space-y-3"><figcaption className="font-semibold">Trước · {selected.batch}{selected.slot}</figcaption>
          <ImagePreview assetId={selected.job.output_asset_ids[0]} title="Concept nguồn" /><DownloadLinks assetId={selected.job.output_asset_ids[0]} />
        </figure>
        <div className="space-y-6"><h3 className="font-semibold">Sau · Lịch sử nâng cấp</h3>
          {!history.length && <p>Chưa có bản nâng cấp. Chọn kích thước và tạo bản đầu tiên.</p>}
          {history.map(v => <article key={v.id} className="space-y-3 rounded-lg border p-4" aria-label={`Bản nâng cấp ${v.number}`}>
            <h4>Bản nâng cấp {v.number}{v.stale ? ' · Master cũ' : ''}</h4>
            {!v.job.output_asset_ids.length && <JobPlaceholder job={v.job} />}
            {v.job.output_asset_ids[0] && <><ImagePreview assetId={v.job.output_asset_ids[0]} title={`Bản nâng cấp ${v.number}`} compareAssetId={selected.job.output_asset_ids[0]} /><DownloadLinks assetId={v.job.output_asset_ids[0]} /></>}
            <JobDetails job={v.job} projectId={project.id} />
          </article>)}
        </div>
      </div>
    </>}
  </section>
}
