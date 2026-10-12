import { useImageSize } from '@/lib/imageSize'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { request, useProviders, type Concept, type Enhancement, type ProjectDetail, type ReferencePlan } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { active, costLabel, DownloadLinks, ImagePreview, JobDetails, JobPlaceholder, PromptEditor, useGenerationAction } from '@/components/GenerationUI'

export default function EnhanceStep({ project, selectedConceptId, onSelect, onBack }: { project: ProjectDetail; selectedConceptId: string | null; onSelect: (id: string) => void; onBack?: () => void }) {
  const base = `/projects/${project.id}`
  const [size] = useImageSize(project.id)
  const [prompt, setPrompt] = useState('')
  // Empty = polish the concept itself; otherwise iterate on that earlier enhancement.
  const [fromEnhancement, setFromEnhancement] = useState('')
  const [confirmedPlan, setConfirmedPlan] = useState<string | null>(null)
  const concepts = useQuery({ queryKey: ['concepts', project.id], queryFn: () => request<Concept[]>(`${base}/concepts`), refetchInterval: 1500 })
  const versions = useQuery({ queryKey: ['enhancements', project.id], queryFn: () => request<Enhancement[]>(`${base}/enhancements`), refetchInterval: 1500 })
  const successful = concepts.data?.filter(c => c.job.status === 'succeeded') ?? []
  const picked = successful.find(c => c.id === selectedConceptId)
    ?? successful.find(c => c.id === versions.data?.[0]?.concept_id)
    ?? successful[0]
  // Regenerating a slot makes a new revision; always enhance the newest image of that slot,
  // never the one that happened to be selected before.
  const selected = picked
    ? successful.filter(c => c.run === picked.run && c.slot === picked.slot)
        .sort((a, b) => b.revision - a.revision)[0] ?? picked
    : picked
  const planQuery = new URLSearchParams({ ...(size ? { size } : {}), ...(fromEnhancement ? { from_enhancement_id: fromEnhancement } : {}) }).toString()
  const planPath = `${base}/concepts/${selected?.id}/enhance-plan${planQuery ? `?${planQuery}` : ''}`
  const plan = useQuery({ queryKey: ['enhance-plan', project.id, selected?.id, project.provider, project.model, size, fromEnhancement],
    enabled: Boolean(selected), queryFn: () => request<ReferencePlan>(planPath), refetchInterval: 3000 })
  const providers = useProviders()
  const model = providers.data?.find(p => p.name === project.provider)?.models.find(m => m.id === project.model)
  const action = useGenerationAction(project.id)
  const signature = JSON.stringify([selected?.id, project.provider, project.model, size, fromEnhancement, plan.data?.reference_asset_ids, plan.data?.omitted_asset_ids])
  const confirmed = confirmedPlan === signature
  const history = versions.data?.filter(v => v.concept_id === selected?.id) ?? []

  return <section className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-xl font-semibold">Nâng cấp một concept</h2>
      {onBack && <Button size="sm" variant="outline" onClick={onBack}>Quay lại chọn concept</Button>}
    </div>
    <p className="text-sm text-muted-foreground">Tạo lại một ảnh 3:4 độc lập, giữ cảnh, trang phục, tư thế, biểu cảm và góc máy. Nhân vật gốc đã duyệt là nguồn nhận diện chính.</p>
    <PromptEditor projectId={project.id} name="enhance" />
    {concepts.error && <ErrorAlert error={concepts.error} title="Không tải được concept" />}
    {versions.error && <ErrorAlert error={versions.error} title="Không tải được bản nâng cấp" />}
    {!concepts.isPending && !successful.length && <p className="rounded-lg bg-muted p-8 text-center">Tạo thành công ít nhất một concept ở bước 4 để nâng cấp.</p>}
    {selected && <>
      <label className="block text-sm">Concept nguồn <select aria-label="Concept nguồn" className="mt-2 block w-full rounded border p-2" value={selected.id} onChange={e => onSelect(e.target.value)}>
        {successful.map(c => <option key={c.id} value={c.id}>{c.slot}. {c.mood} · Đợt {c.run}, bản {c.revision}{c.stale ? ' (master cũ)' : ''}</option>)}
      </select></label>
      {picked && selected.id !== picked.id && <p className="text-sm text-muted-foreground">
        Đang dùng bản mới nhất của ô {selected.slot} (bản {selected.revision}).
      </p>}
      {selected.stale && <p className="text-sm text-amber-700">Concept nguồn dùng master cũ. Bản nâng cấp sẽ giữ cảnh và dùng nhân vật gốc đã duyệt hiện tại.</p>}
      <div className="flex flex-wrap items-center gap-4 rounded-lg border p-4">
        <span className="text-sm">{model?.display_name} · {costLabel(plan.data?.estimated_cost_usd)} / ảnh · 3:4</span>
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
      {history.length > 0 && <label className="grid gap-1 text-sm">
        Ảnh nguồn để nâng cấp
        <select aria-label="Ảnh nguồn để nâng cấp" className="rounded border p-2"
          value={fromEnhancement} onChange={e => setFromEnhancement(e.target.value)}>
          <option value="">Concept gốc · {selected.slot}. {selected.mood}</option>
          {history.filter(v => v.job.status === 'succeeded').map(v =>
            <option key={v.id} value={v.id}>Bản nâng cấp {v.number}</option>)}
        </select>
        <span className="text-xs text-muted-foreground">
          Chọn một bản nâng cấp để chỉnh tiếp trên kết quả đó thay vì làm lại từ concept gốc.
        </span>
      </label>}
      <label className="grid gap-1 text-sm">
        Yêu cầu nâng cấp
        <Textarea
          aria-label="Yêu cầu nâng cấp"
          rows={3}
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder="Mô tả thay đổi bạn muốn cho ảnh này. Để trống sẽ dùng prompt mặc định của ứng dụng."
        />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <Button disabled={action.isPending || !plan.data || plan.isError || !project.rights_confirmed || Boolean(plan.data.warning && !confirmed) || history.some(v => active(v.job))}
          onClick={() => action.mutate({ path: `${base}/concepts/${selected.id}/enhance`, data: { size: size || null, confirm_reference_subset: confirmed, prompt: prompt.trim() || null, from_enhancement_id: fromEnhancement || null } })}>Nâng cấp concept đã chọn</Button>
        <span className="text-sm text-muted-foreground">{costLabel(plan.data?.estimated_cost_usd)} / ảnh</span>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <figure className="space-y-3"><figcaption className="font-semibold">Trước · {selected.slot}. {selected.mood}</figcaption>
          <ImagePreview assetId={selected.job.output_asset_ids[0]} title="Concept nguồn" /><DownloadLinks assetId={selected.job.output_asset_ids[0]} />
        </figure>
        <div className="space-y-6"><h3 className="font-semibold">Sau · Lịch sử nâng cấp</h3>
          {!history.length && <p>Chưa có bản nâng cấp. Chọn kích thước và tạo bản đầu tiên.</p>}
          {history.map(v => <article key={v.id} className="space-y-3 rounded-lg border p-4" aria-label={`Bản nâng cấp ${v.number}`}>
            <h4>Bản nâng cấp {v.number}{v.stale ? ' · Master cũ' : ''}</h4>
            {!v.job.output_asset_ids.length && <JobPlaceholder job={v.job} />}
            {v.job.output_asset_ids[0] && <><ImagePreview assetId={v.job.output_asset_ids[0]} title={`Bản nâng cấp ${v.number}`} compareAssetId={selected.job.output_asset_ids[0]} /><DownloadLinks assetId={v.job.output_asset_ids[0]} /></>}
            <JobDetails job={v.job} projectId={project.id} />
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline"
                disabled={action.isPending || active(v.job) || !project.rights_confirmed}
                onClick={() => action.mutate({
                  path: `${base}/concepts/${selected.id}/enhance`,
                  // Same source and same wording as this version, for another attempt at it.
                  data: {
                    // Empty strings must become null, or the provider rejects the size outright.
                    size: (v.job.settings.size as string | undefined) || size || null,
                    confirm_reference_subset: true,
                    prompt: v.job.meta.custom_prompt ? v.job.prompt : null,
                    from_enhancement_id: (v.job.meta.from_enhancement_id as string | null) ?? null,
                  },
                })}>
                Tạo lại bản này
              </Button>
              <Button size="sm" variant="ghost"
                disabled={v.job.status !== 'succeeded'}
                onClick={() => { setFromEnhancement(v.id); setPrompt('') }}>
                Chỉnh tiếp từ bản này
              </Button>
            </div>
          </article>)}
        </div>
      </div>
    </>}
  </section>
}
