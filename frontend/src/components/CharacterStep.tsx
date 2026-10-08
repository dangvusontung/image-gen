import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { defaultGenerationSize } from '@/lib/generationPolicy'
import { request, useProviders, type ProjectDetail, type GenerationJob } from '@/api/client'
import { DownloadLinks, ImagePreview, JobDetails, JobPlaceholder } from '@/components/GenerationUI'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

type Job = GenerationJob
interface Master { id: string; round: number; variant: number; job: Job }
interface Turnaround {
  id: string; number: number; stale: boolean; master_version_id: string
  views: { angle: string; job: Job }[]
}
interface Workflow {
  approved_master_id: string | null; approved_turnaround_id: string | null
  masters: Master[]; turnarounds: Turnaround[]
  approvals: { target_type: string; target_id: string; created_at: string }[]
}
const labels: Record<string, string> = {
  front: 'Chính diện 0°', left45: 'Trái 45°', left90: 'Nghiêng trái 90°',
  right45: 'Phải 45°', right90: 'Nghiêng phải 90°', back: 'Sau lưng 180°',
  queued: 'Đang chờ', submitting: 'Đang gửi', polling: 'Đang tạo', running: 'Đang tạo',
  succeeded: 'Hoàn tất', failed: 'Lỗi', cancelled: 'Đã huỷ',
}

function ImageJob({ job, projectId }: { job: Job; projectId: string }) {
  return <div className="space-y-2">
    {!job.output_asset_ids.length && <JobPlaceholder job={job} />}
    {job.output_asset_ids.map(id => <div key={id} className="space-y-2"><ImagePreview assetId={id} /><DownloadLinks assetId={id} /></div>)}
    <JobDetails job={job} projectId={projectId} />
  </div>
}

export default function CharacterStep({ project, step, onApproved }: { onApproved?: () => void; project: ProjectDetail; step: 'master' | 'turnaround' | 'history' }) {
  const qc = useQueryClient()
  const base = `/projects/${project.id}`
  const key = ['workflow', project.id]
  const workflow = useQuery({ queryKey: key, queryFn: () => request<Workflow>(`${base}/workflow`), refetchInterval: 1500 })
  const providers = useProviders()
  const model = providers.data?.find(p => p.name === project.provider)?.models.find(m => m.id === project.model)
  const defaultSize = defaultGenerationSize(project, model?.default_size)
  const unitPrice = (defaultSize ? model?.price_table?.[defaultSize] : undefined) ?? model?.price_per_image_usd
  const [variants, setVariants] = useState(1)
  const [confirmed, setConfirmed] = useState(false)
  const [body, setBody] = useState('')
  const prompt = useQuery({ queryKey: ['prompt', project.id, step], enabled: step !== 'history',
    queryFn: () => request<{ body: string }>(`/prompts/${step}?project_id=${project.id}`) })
  useEffect(() => { if (prompt.data) setBody(prompt.data.body) }, [prompt.data])
  const action = useMutation({
    mutationFn: ({ path, data, method = 'POST' }: { path: string; data?: unknown; method?: string }) =>
      request(path, { method, headers: { 'Content-Type': 'application/json' }, body: data === undefined ? undefined : JSON.stringify(data) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: key })
      qc.invalidateQueries({ queryKey: ['prompt', project.id, step] })
    },
  })
  const run = (path: string, data?: unknown, method?: string, onSuccess?: () => void) => action.mutate({ path, data, method }, { onSuccess })
  const data = workflow.data
  const count = step === 'master' ? variants : 6
  const paid = project.provider !== 'mock'
  const needConfirmation = paid && count > 1
  const ready = project.rights_confirmed && (step === 'master' ? project.assets.length > 0 : Boolean(data?.approved_master_id))
  const estimate = useQuery({ queryKey: ['estimate', project.id, project.provider, project.model, step, count], enabled: step !== 'history' && ready,
    queryFn: () => request<{ total_usd: number | null; note: string }>(`${base}/generation-estimate?purpose=${step}&count=${count}`), refetchInterval: 3000 })
  const pending = action.isPending

  return <section className="space-y-5">
    {workflow.error && <ErrorAlert error={workflow.error} title="Không tải được lịch sử" />}
    {action.error && <ErrorAlert error={action.error} title="Thao tác không thành công" />}
    {step !== 'history' && <>
      <h2 className="text-xl font-semibold">{step === 'master' ? 'Tạo và duyệt nhân vật gốc' : 'Turnaround sáu góc'}</h2>
      {step === 'master' && project.assets.length < 3 && <p role="status">Nên dùng 3–8 ảnh để giữ nhận diện nhất quán.</p>}
      {step === 'turnaround' && <p>Turnaround là suy luận của AI. Nhân vật gốc đã duyệt luôn là nguồn nhận diện chính.</p>}
      {!ready && <p>{!project.rights_confirmed ? 'Xác nhận quyền sử dụng ảnh ở bước 1.' : step === 'master' ? 'Tải ảnh tham chiếu ở bước 1.' : 'Tạo và duyệt nhân vật gốc ở bước 2.'}</p>}
      {paid && <p className="text-sm">{model?.display_name}{defaultSize ? ` · ${defaultSize}` : ''} · Ảnh tham chiếu sẽ được gửi tới nhà cung cấp đã chọn.</p>}
      <details className="space-y-3 rounded-lg border p-4"><summary>Chỉnh sửa prompt</summary>
        {prompt.error && <ErrorAlert error={prompt.error} title="Không tải được prompt" />}
        <Textarea aria-label="Prompt" value={body} onChange={e => setBody(e.target.value)} rows={7} />
        <div className="flex gap-2">
          <Button disabled={pending || !body.trim()} onClick={() => run(`/prompts/${step}?project_id=${project.id}`, { body }, 'PUT')}>Lưu prompt</Button>
          <Button variant="outline" disabled={pending} onClick={() => run(`/prompts/${step}?project_id=${project.id}`, { body: null }, 'PUT')}>Đặt lại mặc định</Button>
        </div>
        <p className="text-xs">Lưu thay đổi trước khi tạo ảnh.</p>
      </details>
      <div className="flex flex-wrap items-center gap-4">
        {step === 'master' && <label>Số biến thể <select aria-label="Số biến thể" className="rounded border p-2" value={variants} onChange={e => { setVariants(Number(e.target.value)); setConfirmed(false) }}>
          {[1, 2, 3, 4].map(n => <option key={n}>{n}</option>)}
        </select></label>}
        <p className="text-sm">{(estimate.data ? estimate.data.total_usd : unitPrice != null ? unitPrice * count : null) != null ? `Ước tính: $${(estimate.data?.total_usd ?? (unitPrice ?? 0) * count).toFixed(3)} / ${count} ảnh` : 'Chi phí ước tính chưa có'}</p>
        {needConfirmation && <label className="text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> Tôi xác nhận tạo {count} ảnh và chi phí nhà cung cấp</label>}
        <Button disabled={pending || !ready || (needConfirmation && !confirmed)} onClick={() => run(`${base}/${step}/generate`, { variants, confirmed })}>Tạo {step === 'master' ? 'nhân vật gốc' : 'sáu góc'}</Button>
      </div>
      {estimate.data && <p className="text-xs text-muted-foreground">{estimate.data.note}</p>}
    </>}
    {step === 'master' && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {data?.masters.map(m => <article key={m.id} className="space-y-3 rounded-xl border p-4">
        <h3>Lần {m.round} · Biến thể {m.variant}</h3><ImageJob job={m.job} projectId={project.id} />
        <Button disabled={pending || m.job.status !== 'succeeded' || data.approved_master_id === m.id} onClick={() => run(`${base}/master/${m.id}/approve`, undefined, undefined, onApproved)}>{data.approved_master_id === m.id ? 'Đã duyệt' : 'Duyệt nhân vật này'}</Button>
        {['failed', 'cancelled'].includes(m.job.status) && <Button variant="outline" disabled={pending} onClick={() => run(`${base}/master/generate`, { variants: 1 })}>Tạo lại từ ảnh tham chiếu</Button>}
      </article>)}
    </div>}
    {step === 'turnaround' && data?.turnarounds.map(t => <article key={t.id} className="space-y-4 rounded-xl border p-4">
      <h3>Phiên bản {t.number}{t.stale ? ' · Dựa trên nhân vật gốc cũ' : ''}</h3>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{t.views.map(v => <div key={v.angle} className="space-y-3">
        <h4>{labels[v.angle]}</h4><ImageJob job={v.job} projectId={project.id} />
        <Button variant="outline" disabled={pending || t.stale} onClick={() => run(`${base}/turnaround/${t.id}/views/${v.angle}/regenerate`)}>Tạo lại góc này</Button>
      </div>)}</div>
      <Button disabled={pending || t.stale || t.views.length !== 6 || t.views.some(v => v.job.status !== 'succeeded') || data.approved_turnaround_id === t.id} onClick={() => run(`${base}/turnaround/${t.id}/approve`, undefined, undefined, onApproved)}>{data.approved_turnaround_id === t.id ? 'Đã duyệt' : 'Duyệt sáu góc'}</Button>
    </article>)}
    {step === 'history' && <div className="space-y-3"><h2 className="text-xl font-semibold">Lịch sử phê duyệt</h2>
      {!data?.approvals.length && <p>Chưa có phê duyệt.</p>}
      {data?.approvals.map((e, i) => <p key={i}>{new Date(e.created_at).toLocaleString('vi-VN')} · {e.target_type === 'master' ? 'Nhân vật gốc' : 'Turnaround'} · {e.target_id}</p>)}
    </div>}
  </section>
}
