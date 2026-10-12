import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { defaultGenerationSize } from '@/lib/generationPolicy'
import { request, useProviders, type ProjectDetail, type GenerationJob } from '@/api/client'
import { DownloadLinks, ImagePreview, JobDetails, JobPlaceholder, type GalleryImage } from '@/components/GenerationUI'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'

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
const ANGLE_KEYS = ['front', 'left45', 'left90', 'right45', 'right90', 'back']

const labels: Record<string, string> = {
  front: 'Chính diện 0°', left45: 'Trái 45°', left90: 'Nghiêng trái 90°',
  right45: 'Phải 45°', right90: 'Nghiêng phải 90°', back: 'Sau lưng 180°',
  queued: 'Đang chờ', submitting: 'Đang gửi', polling: 'Đang tạo', running: 'Đang tạo',
  succeeded: 'Hoàn tất', failed: 'Lỗi', cancelled: 'Đã huỷ',
}

function ImageJob({ job, projectId, gallery }: { job: Job; projectId: string; gallery?: GalleryImage[] }) {
  return <div className="space-y-2">
    {!job.output_asset_ids.length && <JobPlaceholder job={job} />}
    {job.output_asset_ids.map(id => <div key={id} className="space-y-2"><ImagePreview assetId={id} gallery={gallery} /><DownloadLinks assetId={id} /></div>)}
    <JobDetails job={job} projectId={projectId} />
  </div>
}

export default function CharacterStep({ project, step, onApproved, onSkip }: { onApproved?: () => void; onSkip?: () => void; project: ProjectDetail; step: 'master' | 'turnaround' | 'history' }) {
  const qc = useQueryClient()
  const base = `/projects/${project.id}`
  const key = ['workflow', project.id]
  const workflow = useQuery({ queryKey: key, queryFn: () => request<Workflow>(`${base}/workflow`), refetchInterval: 1500 })
  const providers = useProviders()
  const model = providers.data?.find(p => p.name === project.provider)?.models.find(m => m.id === project.model)
  const defaultSize = defaultGenerationSize(project, model?.default_size)
  const unitPrice = (defaultSize ? model?.price_table?.[defaultSize] : undefined) ?? model?.price_per_image_usd
  const [variants, setVariants] = useState(1)
  const [angles, setAngles] = useState<string[]>(ANGLE_KEYS)
  const [confirmed, setConfirmed] = useState(false)
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
  const count = step === 'master' ? variants : angles.length
  const paid = project.provider !== 'mock'
  const needConfirmation = paid && count > 1
  const selectedAssets = project.assets.filter(a => a.selected)
  const ready = project.rights_confirmed && (step === 'master' ? selectedAssets.length > 0 : Boolean(data?.approved_master_id))
  const estimate = useQuery({ queryKey: ['estimate', project.id, project.provider, project.model, step, count], enabled: step !== 'history' && ready,
    queryFn: () => request<{ total_usd: number | null; note: string }>(`${base}/generation-estimate?purpose=${step}&count=${count}`), refetchInterval: 3000 })
  const pending = action.isPending
  // One generation = one round: every "Tạo nhân vật gốc" run, with all of its variants.
  const generations = Object.values(
    (data?.masters ?? []).reduce<Record<number, Master[]>>((acc, m) => ((acc[m.round] ??= []).push(m), acc), {}),
  )
    .map(group => [...group].sort((a, b) => a.variant - b.variant))
    .sort((a, b) => b[0].round - a[0].round)
  // Every finished variant, in the order shown, so the enlarged view can page across generations.
  const masterGallery: GalleryImage[] = generations.flat().flatMap(m =>
    m.job.output_asset_ids.map(id => ({ assetId: id, title: `Lần tạo ${m.round} · Biến thể ${m.variant}` })),
  )

  return <section className="space-y-5">
    {workflow.error && <ErrorAlert error={workflow.error} title="Không tải được lịch sử" />}
    {action.error && <ErrorAlert error={action.error} title="Thao tác không thành công" />}
    {step !== 'history' && <>
      <h2 className="text-xl font-semibold">{step === 'master' ? 'Tạo và duyệt nhân vật gốc' : 'Turnaround sáu góc'}</h2>
      {step === 'master' && selectedAssets.length > 0 && selectedAssets.length < 3 && <p role="status">Nên dùng 3–8 ảnh để giữ nhận diện nhất quán (đang chọn {selectedAssets.length}).</p>}
      {step === 'turnaround' && <div className="space-y-2">
        <p>Turnaround là bước tùy chọn. Bạn có thể tạo các góc cần thiết hoặc bỏ qua để tạo concept từ nhân vật gốc đã duyệt.</p>
        <Button variant="outline" disabled={!ready} onClick={onSkip}>Bỏ qua → Concept</Button>
      </div>}
      {!ready && <p>{!project.rights_confirmed ? 'Xác nhận quyền sử dụng ảnh ở bước 1.' : step === 'master' ? (project.assets.length ? 'Chọn ít nhất một ảnh ở bước 1.' : 'Tải ảnh tham chiếu ở bước 1.') : 'Tạo và duyệt nhân vật gốc ở bước 2.'}</p>}
      {paid && <p className="text-sm">{model?.display_name}{defaultSize ? ` · ${defaultSize}` : ''} · {step === 'master' ? `${selectedAssets.length} ảnh tham chiếu đã chọn sẽ được gửi` : 'Ảnh tham chiếu sẽ được gửi'} tới nhà cung cấp đã chọn.</p>}
      <div className="flex flex-wrap items-center gap-4">
        {step === 'master' && <label>Số biến thể <select aria-label="Số biến thể" className="rounded border p-2" value={variants} onChange={e => { setVariants(Number(e.target.value)); setConfirmed(false) }}>
          {[1, 2, 3, 4].map(n => <option key={n}>{n}</option>)}
        </select></label>}
        {step === 'turnaround' && <fieldset className="flex flex-wrap items-center gap-3">
          <legend className="sr-only">Góc cần tạo</legend>
          <span className="text-sm">Góc cần tạo</span>
          {ANGLE_KEYS.map(key => <label key={key} className="text-sm">
            <input type="checkbox" aria-label={labels[key]} checked={angles.includes(key)}
              onChange={e => {
                setAngles(prev => e.target.checked ? ANGLE_KEYS.filter(k => prev.includes(k) || k === key) : prev.filter(k => k !== key))
                setConfirmed(false)
              }} /> {labels[key]}
          </label>)}
        </fieldset>}
        <p className="text-sm">{(estimate.data ? estimate.data.total_usd : unitPrice != null ? unitPrice * count : null) != null ? `Ước tính: $${(estimate.data?.total_usd ?? (unitPrice ?? 0) * count).toFixed(3)} / ${count} ảnh` : 'Chi phí ước tính chưa có'}</p>
        {needConfirmation && <label className="text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> Tôi xác nhận tạo {count} ảnh và chi phí nhà cung cấp</label>}
        <Button disabled={pending || !ready || !count || (needConfirmation && !confirmed)}
          onClick={() => run(`${base}/${step}/generate`, step === 'master' ? { variants, confirmed } : { confirmed, angles })}>
          Tạo {step === 'master' ? 'nhân vật gốc' : `${angles.length} góc`}
        </Button>
      </div>
      {estimate.data && <p className="text-xs text-muted-foreground">{estimate.data.note}</p>}
    </>}
    {step === 'master' && <div className="space-y-6">
      {generations.map(group => <section key={group[0].round} className="space-y-3" aria-label={`Lần tạo ${group[0].round}`}>
        <div className="flex flex-wrap items-center gap-2 border-b pb-2">
          <h3 className="font-semibold">Lần tạo {group[0].round}</h3>
          <time className="text-sm text-muted-foreground" dateTime={group[0].job.created_at}>{new Date(group[0].job.created_at).toLocaleString('vi-VN')}</time>
          <span className="text-sm text-muted-foreground">· {group.length} biến thể</span>
          {group.some(m => m.id === data?.approved_master_id) && <span className="text-sm text-emerald-700">· Chứa bản đã duyệt</span>}
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {group.map(m => <article key={m.id} className="space-y-3 rounded-xl border p-4">
            <h4>Biến thể {m.variant}</h4><ImageJob job={m.job} projectId={project.id} gallery={masterGallery} />
            <Button disabled={pending || m.job.status !== 'succeeded' || data?.approved_master_id === m.id} onClick={() => run(`${base}/master/${m.id}/approve`, undefined, undefined, onApproved)}>{data?.approved_master_id === m.id ? 'Đã duyệt' : 'Duyệt nhân vật này'}</Button>
            {['failed', 'cancelled'].includes(m.job.status) && <Button variant="outline" disabled={pending} onClick={() => run(`${base}/master/generate`, { variants: 1 })}>Tạo lại từ ảnh tham chiếu</Button>}
          </article>)}
        </div>
      </section>)}
    </div>}
    {step === 'turnaround' && data?.turnarounds.map(t => <article key={t.id} className="space-y-4 rounded-xl border p-4">
      <h3>Phiên bản {t.number} · {t.views.length} góc{t.stale ? ' · Dựa trên nhân vật gốc cũ' : ''}</h3>
      {t.views[0] && <time className="text-sm text-muted-foreground" dateTime={t.views[0].job.created_at}>{new Date(t.views[0].job.created_at).toLocaleString('vi-VN')}</time>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{t.views.map(v => <div key={v.angle} className="space-y-3">
        <h4>{labels[v.angle]}</h4><ImageJob job={v.job} projectId={project.id} />
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={pending || t.stale} onClick={() => run(`${base}/turnaround/${t.id}/views/${v.angle}/regenerate`)}>Tạo lại góc này</Button>
          <Button variant="ghost" disabled={pending || t.views.length <= 1} onClick={() => run(`${base}/turnaround/${t.id}/views/${v.angle}`, undefined, 'DELETE')}>Bỏ góc này</Button>
        </div>
      </div>)}</div>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          disabled={pending || !t.views.length || t.views.some(v => v.job.status !== 'succeeded') || data.approved_turnaround_id === t.id}
          onClick={() => run(`${base}/turnaround/${t.id}/approve`, { adopt_master: t.stale }, undefined, onApproved)}>
          {data.approved_turnaround_id === t.id ? 'Đang dùng' : t.stale ? 'Dùng bản này và nhân vật gốc của nó' : 'Dùng turnaround này'}
        </Button>
        <Button variant="ghost" disabled={pending}
          onClick={() => { if (confirm(`Xoá turnaround phiên bản ${t.number}? Ảnh vẫn còn trong lịch sử job.`)) run(`${base}/turnaround/${t.id}`, undefined, 'DELETE') }}>
          Xoá phiên bản {t.number}
        </Button>
        {t.stale && <span className="text-sm text-amber-700">
          Bản này dựng từ nhân vật gốc khác — chọn nó sẽ duyệt lại nhân vật gốc đó để khuôn mặt và các góc khớp nhau.
        </span>}
      </div>
    </article>)}
    {step === 'history' && <div className="space-y-3"><h2 className="text-xl font-semibold">Lịch sử phê duyệt</h2>
      {!data?.approvals.length && <p>Chưa có phê duyệt.</p>}
      {data?.approvals.map((e, i) => <p key={i}>{new Date(e.created_at).toLocaleString('vi-VN')} · {e.target_type === 'master' ? 'Nhân vật gốc' : 'Turnaround'} · {e.target_id}</p>)}
    </div>}
  </section>
}
