import { ConceptMenu, useConceptChoices } from '@/components/ConceptMenu'
import { defaultGenerationSize } from '@/lib/generationPolicy'
import { useImageSize } from '@/lib/imageSize'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { request, useProviders, type Concept, type ConceptProposal, type ProjectDetail } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { active, costLabel, DownloadLinks, ImagePreview, JobDetails, JobPlaceholder, PromptEditor, useGenerationAction } from '@/components/GenerationUI'

const BRIEF_FIELDS = ['setting', 'activity', 'pose', 'outfit', 'silhouette', 'expression', 'gaze', 'camera', 'framing', 'lighting']

const BRIEF_LABEL: Record<string, string> = {
  setting: 'Bối cảnh', activity: 'Hoạt động', outfit: 'Trang phục', silhouette: 'Dáng trang phục',
  framing: 'Khung hình', pose: 'Tư thế', expression: 'Biểu cảm', gaze: 'Hướng nhìn',
  camera: 'Máy ảnh', lighting: 'Ánh sáng',
}

/** Edit a blocked concept's wording and try again, instead of retrying the same rejected prompt. */
function FixAndRetry({ concept, projectId, size, choices, disabled }: {
  concept: Concept
  projectId: string
  size: string
  choices: unknown
  disabled: boolean
}) {
  const action = useGenerationAction(projectId)
  const [draft, setDraft] = useState<Record<string, string>>(() => ({ ...concept.brief }))
  const [title, setTitle] = useState(concept.mood)
  const blocked = concept.job.error_code === 'content_moderated'
  const changed = title !== concept.mood || BRIEF_FIELDS.some((f) => (draft[f] ?? '') !== (concept.brief[f] ?? ''))

  return (
    <details className="rounded-lg border p-3 text-sm" open={blocked}>
      <summary>{blocked ? 'Nội dung bị chặn — sửa mô tả rồi tạo lại' : 'Sửa mô tả concept rồi tạo lại'}</summary>
      {blocked && <p className="mt-2 text-xs text-muted-foreground">
        Nhà cung cấp từ chối prompt này. Thử đổi trang phục, tư thế hoặc bối cảnh cho trung tính hơn rồi tạo lại.
      </p>}
      <div className="mt-3 grid gap-2">
        <label className="grid gap-1 text-xs">Tiêu đề
          <input className="rounded border p-2 text-sm" value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        {BRIEF_FIELDS.filter((f) => f in concept.brief).map((field) => (
          <label key={field} className="grid gap-1 text-xs">{BRIEF_LABEL[field] ?? field}
            <input
              className="rounded border p-2 text-sm"
              aria-label={`${BRIEF_LABEL[field] ?? field} của ô ${concept.slot}`}
              value={draft[field] ?? ''}
              onChange={(e) => setDraft({ ...draft, [field]: e.target.value })}
            />
          </label>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" disabled={disabled || action.isPending || !changed}
          onClick={() => action.mutate({
            path: `/projects/${projectId}/concepts/${concept.id}/regenerate`,
            data: { size: size || null, choices, title, brief: draft },
          })}>
          Tạo lại với mô tả mới
        </Button>
        <Button size="sm" variant="ghost" disabled={!changed}
          onClick={() => { setDraft({ ...concept.brief }); setTitle(concept.mood) }}>
          Hoàn tác
        </Button>
      </div>
      {action.error && <ErrorAlert error={action.error} title="Không tạo lại được" />}
    </details>
  )
}

export default function ConceptsStep({ project, onEnhance }: { project: ProjectDetail; onEnhance: (id: string) => void }) {
  const [selectedRun, setSelectedRun] = useState<number | null>(null)
  const [compact, setCompact] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [size] = useImageSize(project.id)
  // null = every concept; an array = exactly those slots, including none at all.
  const [picked, setPicked] = useState<number[] | null>(null)
  const [customCount, setCustomCount] = useState(1)
  const [customConfirmed, setCustomConfirmed] = useState(false)
  const editsKey = `concept-edits:${project.id}`
  const [edits, setEdits] = useState<Record<number, Record<string, string>>>(() => {
    try { return JSON.parse(localStorage.getItem(editsKey) || '{}') } catch { return {} }
  })
  const saveEdits = (next: Record<number, Record<string, string>>) => {
    setEdits(next)
    try { localStorage.setItem(editsKey, JSON.stringify(next)) } catch { /* storage may be unavailable */ }
  }
  const fieldOf = (slot: number, field: string, original: string) => edits[slot]?.[field] ?? original
  const editField = (slot: number, field: string, value: string) =>
    saveEdits({ ...edits, [slot]: { ...edits[slot], [field]: value } })
  const [choices, setChoices] = useConceptChoices(project.id)
  const base = `/projects/${project.id}`
  const concepts = useQuery({ queryKey: ['concepts', project.id], queryFn: () => request<Concept[]>(`${base}/concepts`), refetchInterval: 1500 })
  const proposals = useQuery({ queryKey: ['concept-proposals', project.id], queryFn: () => request<ConceptProposal[]>(`${base}/concept-proposals`), refetchInterval: 3000 })
  const workflow = useQuery({ queryKey: ['workflow', project.id], queryFn: () => request<{ approved_master_id: string | null }>(`${base}/workflow`), refetchInterval: 1500 })
  const providers = useProviders()
  const provider = providers.data?.find(p => p.name === project.provider)
  const model = provider?.models.find(m => m.id === project.model)
  const action = useGenerationAction(project.id)
  const runs = [...new Set(concepts.data?.map(c => c.run) ?? [])].sort((a, b) => b - a)
  const run = selectedRun ?? runs[0]
  const all = concepts.data?.filter(c => c.run === run) ?? []
  const slots = [...new Set(all.map(c => c.slot))].sort((a, b) => a - b)
  const cards = slots.map(slot => all.filter(c => c.slot === slot).sort((a, b) => b.revision - a.revision)[0]).filter(Boolean)
  const paid = project.provider !== 'mock'
  const resolvedSize = size || defaultGenerationSize(project, model?.default_size)
  const unitPrice = (resolvedSize ? model?.price_table?.[resolvedSize] : undefined) ?? model?.price_per_image_usd
  const pending = action.isPending
  const ready = project.rights_confirmed && Boolean(workflow.data?.approved_master_id)
  const list = proposals.data ?? []
  const chosen = picked === null ? list : list.filter(p => picked.includes(p.slot))
  const estimate = useQuery({ queryKey: ['estimate', project.id, project.provider, project.model, size, chosen.length], enabled: ready && chosen.length > 0,
    queryFn: () => request<{ total_usd: number | null; note: string }>(`${base}/generation-estimate?purpose=concept&count=${chosen.length}${size ? `&size=${encodeURIComponent(size)}` : ''}`), refetchInterval: 3000 })

  const builtIn = list.length > 0 && list[0].run === 0
  const generate = () => action.mutate(
    {
      path: `${base}/concepts/generate`,
      data: {
        ...(builtIn ? { slots: chosen.map(p => p.slot) } : { proposal_ids: chosen.map(p => p.id) }),
        confirmed, size: size || null,
        // Only the edited slots travel; everything else keeps its stored wording.
        briefs: Object.fromEntries(chosen.filter(p => edits[p.slot]).map(p => [p.slot, edits[p.slot]])),
        titles: Object.fromEntries(chosen.filter(p => edits[p.slot]?.title).map(p => [p.slot, edits[p.slot].title])),
      },
    },
    { onSuccess: () => setSelectedRun(null) })

  return <section className="space-y-5">
    <h2 className="text-xl font-semibold">Concept</h2>
    {concepts.isPending && <Skeleton className="h-64" />}
    {!!runs.length && <div className="flex flex-wrap items-center gap-4">
      <label>Đợt ảnh <select className="ml-2 rounded border p-2" aria-label="Đợt concept" value={run} onChange={e => setSelectedRun(Number(e.target.value))}>
        {runs.map(n => <option key={n} value={n}>{n}</option>)}
      </select></label>
      <Button variant="outline" onClick={() => setCompact(!compact)}>{compact ? 'Xem thẻ chi tiết' : 'Xem bảng ảnh'}</Button>
      <a className="text-sm underline" href={`/api${base}/contact-sheet?run=${run}`}>Tải bảng ảnh</a>
      <span className="text-sm">{cards.filter(c => c?.job.status === 'succeeded').length}/{cards.length} hoàn tất</span>
    </div>}
    {!!runs.length && <div className={`grid gap-4 ${compact ? 'grid-cols-2 md:grid-cols-3 lg:grid-cols-5' : 'grid-cols-1'}`}>
      {cards.map(c => c ? <article key={c.id} className="space-y-3 rounded-xl border p-4" aria-label={`Concept ${c.slot}`}>
        <div className={compact ? 'space-y-3' : 'grid gap-4 sm:grid-cols-[10rem_minmax(0,1fr)]'}>
          <div className="space-y-2">
        {c.job.output_asset_ids[0] ? <><ImagePreview assetId={c.job.output_asset_ids[0]} title={`Concept ${c.slot} · ${c.mood}`} /><DownloadLinks assetId={c.job.output_asset_ids[0]} /></> : active(c.job) ? <JobPlaceholder job={c.job} /> : <div className="flex aspect-[3/4] items-center justify-center rounded-lg bg-muted text-sm">Chưa có ảnh kết quả</div>}
          </div>
          <div className="min-w-0 space-y-3">
        <h3 className="font-semibold">{c.slot}. {c.mood}</h3>
        <p className="text-sm text-muted-foreground">{c.camera} · Bản {c.revision}</p>
        {c.stale && <p className="text-sm text-amber-700">Dựa trên nhân vật gốc cũ</p>}

        {!compact && <>
          <p className="text-sm">Trang phục: {c.brief.outfit}</p>
          <p className="text-sm">{c.brief.setting} · {c.brief.activity}</p>
          <details className="text-xs"><summary>Chi tiết concept và phiên bản trước</summary>
            <dl className="mt-2 space-y-1">{Object.entries(c.brief).filter(([, v]) => v).map(([k, v]) => <div key={k}><dt className="inline font-medium">{BRIEF_LABEL[k] ?? k}: </dt><dd className="inline">{v}</dd></div>)}</dl>
            {all.filter(p => p.slot === c.slot && p.id !== c.id).map(p => <div key={p.id} className="mt-3 border-t pt-3"><p>Bản {p.revision}</p>{p.job.output_asset_ids[0] && <><ImagePreview assetId={p.job.output_asset_ids[0]} title={`Concept ${p.slot} bản ${p.revision}`} /><Button size="sm" variant="outline" onClick={() => onEnhance(p.id)}>Nâng cấp bản {p.revision}</Button></>}<JobDetails job={p.job} projectId={project.id} /></div>)}
          </details>
          <JobDetails job={c.job} projectId={project.id} />
        </>}
        {!compact && ['failed', 'cancelled'].includes(c.job.status) &&
          <FixAndRetry concept={c} projectId={project.id} size={size} choices={choices} disabled={!ready} />}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={pending || active(c.job) || !ready} onClick={() => action.mutate({ path: `${base}/concepts/${c.id}/regenerate`, data: { size: size || null } })}>Tạo lại ô {c.slot}</Button>
          <Button size="sm" disabled={c.job.status !== 'succeeded'} onClick={() => onEnhance(c.id)}>Nâng cấp ô {c.slot}</Button>
        </div>
          </div>
        </div>
      </article> : null)}
    </div>}
    <PromptEditor projectId={project.id} name="concept" />
    <p className="text-sm text-muted-foreground">
      9 concept lối sống khác nhau, mỗi concept một bối cảnh, hoạt động, trang phục và ánh sáng riêng.
      Chọn concept bạn muốn rồi tạo ảnh — không cần bước nào khác.
    </p>

    {!ready && <p className="text-sm">Xác nhận quyền sử dụng ảnh và duyệt nhân vật gốc để tiếp tục.</p>}

    {action.error && <ErrorAlert error={action.error} title="Thao tác không thành công" />}
    {proposals.error && <ErrorAlert error={proposals.error} title="Không tải được đề xuất" />}
    {concepts.error && <ErrorAlert error={concepts.error} title="Không tải được concept" />}
    {workflow.error && <ErrorAlert error={workflow.error} title="Không tải được nhân vật gốc" />}

    {list.length > 0 && <details className="space-y-4 rounded-xl border p-4">
      <summary className="cursor-pointer font-semibold">9 concept · Mở/đóng danh sách</summary>
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-semibold">{builtIn ? '9 concept mặc định' : `Đề xuất đợt ${list[0].run}`}</h3>
        {!builtIn && <time className="text-sm text-muted-foreground" dateTime={list[0].created_at}>{new Date(list[0].created_at).toLocaleString('vi-VN')}</time>}
        <Button size="sm" variant="outline" onClick={() => setPicked(null)} disabled={picked === null}>Chọn tất cả</Button>
        <Button size="sm" variant="outline" onClick={() => { setPicked([]); setConfirmed(false) }} disabled={chosen.length === 0}>Bỏ chọn tất cả</Button>
        <span className="text-sm text-muted-foreground">Đang chọn {chosen.length}/{list.length}</span>
      </div>
      <ul className="space-y-3">
        {list.map(p => <li key={p.id} className={`rounded-xl border p-3 text-sm ${picked !== null && !picked.includes(p.slot) ? 'opacity-60' : ''}`}>
          <label className="flex items-start gap-2 font-medium">
            <input type="checkbox" aria-label={`Chọn concept ${p.slot}`} className="mt-1"
              checked={picked === null || picked.includes(p.slot)}
              onChange={e => {
                const current = picked ?? list.map(x => x.slot)
                const next = e.target.checked ? [...new Set([...current, p.slot])] : current.filter(s => s !== p.slot)
                setPicked(next.length === list.length ? null : next)
                setConfirmed(false)
              }} />
            <span>{p.slot}. {fieldOf(p.slot, 'title', p.title)}{edits[p.slot] ? ' · đã sửa' : ''}</span>
          </label>
          <dl className="mt-2 space-y-0.5 pl-6 text-xs text-muted-foreground">
            {Object.entries(p.brief).filter(([, v]) => v).map(([k, v]) => <div key={k}>
              <dt className="inline font-medium">{BRIEF_LABEL[k] ?? k}: </dt>
              <dd className="inline">{fieldOf(p.slot, k, v)}</dd>
            </div>)}
          </dl>
          <details className="mt-2 pl-6 text-xs">
            <summary className="cursor-pointer">Sửa concept này</summary>
            <div className="mt-2 grid gap-2">
              {Object.entries(p.brief).filter(([, v]) => v).map(([k, v]) => (
                <label key={k} className="grid gap-1">{BRIEF_LABEL[k] ?? k}
                  <input
                    className="rounded border p-1.5 text-sm"
                    aria-label={`${BRIEF_LABEL[k] ?? k} của concept ${p.slot}`}
                    value={fieldOf(p.slot, k, v)}
                    onChange={e => editField(p.slot, k, e.target.value)}
                  />
                </label>
              ))}
              {edits[p.slot] && <Button size="sm" variant="ghost" className="justify-self-start"
                onClick={() => { const next = { ...edits }; delete next[p.slot]; saveEdits(next) }}>
                Hoàn tác về mặc định
              </Button>}
            </div>
          </details>
        </li>)}
      </ul>


      <div className="flex flex-wrap items-center gap-4 rounded-lg border p-4">
        <p className="text-sm">{costLabel(estimate.data ? estimate.data.total_usd : unitPrice == null ? null : unitPrice * chosen.length)} / {chosen.length} ảnh</p>
        {paid && <label className="text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> Xác nhận chi phí và gửi ảnh tới nhà cung cấp</label>}
        <Button disabled={pending || !ready || !chosen.length || (paid && !confirmed) || (choices.outfit === 'custom' && !choices.custom_outfit.trim()) || (choices.scene === 'custom' && !choices.custom_scene.trim())} onClick={generate}>
          Tạo ảnh cho {chosen.length} concept
        </Button>
      </div>
      {estimate.data && <p className="text-xs text-muted-foreground">{estimate.data.note}</p>}
    </details>}

    {proposals.isPending && <Skeleton className="h-40" />}


    <details className="rounded-lg border p-4">
      <summary className="font-medium">Ảnh tùy chỉnh · tự chọn trang phục và bối cảnh</summary>
      <p className="mt-2 text-sm text-muted-foreground">
        Tạo ảnh riêng từ menu bên dưới, không liên quan tới 9 concept ở trên.
      </p>
      <div className="mt-3 space-y-3">
        <ConceptMenu projectId={project.id} choices={choices} onChange={value => { setChoices(value); setCustomConfirmed(false) }} />
        <div className="flex flex-wrap items-center gap-4 rounded-lg border p-4">
          <label className="text-sm">Số ảnh
            <select aria-label="Số ảnh tùy chỉnh" className="ml-2 rounded border p-2" value={customCount}
              onChange={e => { setCustomCount(Number(e.target.value)); setCustomConfirmed(false) }}>
              {[1, 2, 3, 4].map(n => <option key={n}>{n}</option>)}
            </select>
          </label>
          {paid && <label className="text-sm">
            <input type="checkbox" checked={customConfirmed} onChange={e => setCustomConfirmed(e.target.checked)} /> Xác nhận chi phí
          </label>}
          <Button disabled={pending || !ready || (paid && !customConfirmed)
            || (choices.outfit === 'custom' && !choices.custom_outfit.trim())
            || (choices.scene === 'custom' && !choices.custom_scene.trim())}
            onClick={() => action.mutate({
              path: `${base}/concepts/generate`,
              data: { custom: true, count: customCount, choices, confirmed: customConfirmed, size: size || null },
            }, { onSuccess: () => setSelectedRun(null) })}>
            Tạo {customCount} ảnh tùy chỉnh
          </Button>
        </div>
      </div>
    </details>


  </section>
}
