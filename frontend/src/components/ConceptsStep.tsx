import { isArchivedConcept, matchesConceptArchive, type ConceptArchiveFilter } from '@/lib/conceptArchive'
import { conceptProgress, matchesProgress, progressLabel } from '@/lib/conceptProgress'
import { CONCEPT_EMOJIS, CONCEPT_EMOJI_STORAGE, conceptMarkKey, readEmojiMarks } from '@/lib/conceptEmoji'
import { conceptDisplayNumbers, groupConcepts } from '@/lib/conceptGroups'
import EditConceptPrompt from '@/components/EditConceptPrompt'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import CopyConceptConfiguration from '@/components/CopyConceptConfiguration'
import { ConceptMenu, OutfitSwitcher, useConceptChoices, type ConceptChoices } from '@/components/ConceptMenu'
import { defaultGenerationSize } from '@/lib/generationPolicy'
import { useImageSize } from '@/lib/imageSize'
import { Fragment, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { assetUrl, request, useProviders, type Concept, type ConceptProposal, type ProjectDetail } from '@/api/client'
import { apiUrl } from '@/lib/backend'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { active, costLabel, DownloadLinks, ImagePreview, JobDetails, JobPlaceholder, PromptEditor, useGenerationAction } from '@/components/GenerationUI'

function CompactDescription({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false)
  if (!text) return null
  return <div className="min-w-0 text-xs text-muted-foreground">
    <p className={expanded ? 'break-words whitespace-pre-wrap' : 'line-clamp-2 break-words'}>{text}</p>
    <button type="button" className="mt-1 underline underline-offset-2" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? 'Thu gọn' : 'Xem thêm'}</button>
  </div>
}

const WARDROBE_FIELDS = ['outfit', 'footwear', 'silhouette']
const BRIEF_FIELDS = ['setting', 'activity', 'pose', 'outfit', 'footwear', 'silhouette', 'expression', 'gaze', 'camera', 'framing', 'lighting']

const BRIEF_LABEL: Record<string, string> = {
  footwear: 'Giày', setting: 'Bối cảnh', activity: 'Hoạt động', outfit: 'Trang phục', silhouette: 'Dáng trang phục',
  framing: 'Khung hình', pose: 'Tư thế', expression: 'Biểu cảm', gaze: 'Hướng nhìn',
  camera: 'Máy ảnh', lighting: 'Ánh sáng',
}

/** Edit a blocked concept's wording and try again, instead of retrying the same rejected prompt. */
function FixAndRetry({ concept, projectId, size, choices, disabled }: {
  concept: Concept
  projectId: string
  size: string
  choices: ConceptChoices
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
        {BRIEF_FIELDS.filter((f) => f in concept.brief && (choices.outfit !== 'master' || !WARDROBE_FIELDS.includes(f))).map((field) => (
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
  const queryClient = useQueryClient()
  const bookmarks = useQuery({ queryKey: ['concept-bookmarks'], queryFn: () => request<{ keys: string[] }>('/concept-bookmarks'), refetchInterval: 3000 })
  const bookmarkKey = (p: ConceptProposal) => p.bookmark_key || conceptMarkKey(project.id, p)
  const bookmarked = (p: ConceptProposal) => bookmarks.data?.keys.includes(bookmarkKey(p)) ?? false
  const bookmarkAction = useMutation({
    mutationFn: ({ key, value }: { key: string; value: boolean }) => request('/concept-bookmarks/' + encodeURIComponent(key), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bookmarked: value }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['concept-bookmarks'] }),
  })
  const toggleBookmark = (p: ConceptProposal) => { if (!bookmarkAction.isPending) bookmarkAction.mutate({ key: bookmarkKey(p), value: !bookmarked(p) }) }
  useEffect(() => {
    const marker = 'concept-bookmarks:be-migrated:' + apiUrl('/concept-bookmarks')
    let active = true
    const migrate = async () => {
      try {
        if (localStorage.getItem(marker)) return
        const saved = JSON.parse(localStorage.getItem('concept-bookmarks:v1') || '{}')
        for (const [key, value] of Object.entries(saved)) {
          if (value === true && /^(default:\d+|project:[a-f0-9-]{36}:run:\d+:slot:\d+)$/.test(key)) {
            await request('/concept-bookmarks/' + encodeURIComponent(key), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bookmarked: true }) })
          }
        }
        localStorage.setItem(marker, '1')
        if (active) await queryClient.invalidateQueries({ queryKey: ['concept-bookmarks'] })
      } catch { /* Keep local bookmarks so the next mount can retry the import. */ }
    }
    void migrate()
    return () => { active = false }
  }, [queryClient])
  const [emojiMarks, setEmojiMarks] = useState(readEmojiMarks)
  const [emojiFilter, setEmojiFilter] = useState('all')
  const emojiOf = (proposal: ConceptProposal) => emojiMarks[conceptMarkKey(project.id, proposal)] ?? ''
  const markEmoji = (proposal: ConceptProposal, emoji: string) => {
    const next = { ...readEmojiMarks(), ...emojiMarks }
    const key = conceptMarkKey(project.id, proposal)
    if (emoji) next[key] = emoji
    else delete next[key]
    setEmojiMarks(next)
    try { localStorage.setItem(CONCEPT_EMOJI_STORAGE, JSON.stringify(next)) } catch { /* Browser storage may be unavailable. */ }
  }
  const [archiveFilter, setArchiveFilter] = useState<ConceptArchiveFilter>('active')
  const [conceptSearch, setConceptSearch] = useState('')
  const [progressFilter, setProgressFilter] = useState('all')
  const [historyKey, setHistoryKey] = useState<string | null>(null)
  const [selectedRun, setSelectedRun] = useState<number | null>(null)
  const [rerunSelection, setRerunSelection] = useState<{ run: number; slots: number[] } | null>(null)
  const [rerunConfirmed, setRerunConfirmed] = useState(false)
  const [useCatalogBriefs, setUseCatalogBriefs] = useState(false)
  const [compact, setCompact] = useState(true)
  const [detailSlot, setDetailSlot] = useState<number | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [savedSize] = useImageSize(project.id)
  const size = project.generation_size || (project.preset_steps?.concept ? '' : savedSize)
  // null = every concept; an array = exactly those slots, including none at all.
  const [picked, setPicked] = useState<number[] | null>([])
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
  const progress = useMemo(() => conceptProgress(concepts.data ?? []), [concepts.data])
  const proposals = useQuery({ queryKey: ['concept-proposals', project.id, archiveFilter], queryFn: () => request<ConceptProposal[]>(`${base}/concept-proposals${archiveFilter === 'active' ? '' : `?status=${archiveFilter}`}`), refetchInterval: 3000 })
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
  const rerunSlots = rerunSelection?.run === run ? slots.filter(slot => rerunSelection.slots.includes(slot)) : []
  const pickForRerun = (next: number[]) => {
    setRerunSelection({ run, slots: next })
    setRerunConfirmed(false)
  }
  const paid = project.provider !== 'mock'
  const resolvedSize = size || defaultGenerationSize(project, model?.default_size)
  const unitPrice = (resolvedSize ? model?.price_table?.[resolvedSize] : undefined) ?? model?.price_per_image_usd
  const pending = action.isPending
  const ready = project.rights_confirmed && Boolean(workflow.data?.approved_master_id)
  const list = (proposals.data ?? []).filter(row => matchesConceptArchive(row, archiveFilter))
  const displayNumbers = conceptDisplayNumbers(list)
  const [groupMode, setGroupMode] = useState<'family' | 'scene'>('family')
  const displayNumber = (slot: number) => displayNumbers.get(slot) ?? slot
  const normalizeSearch = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase()
  const searchTerms = normalizeSearch(conceptSearch).trim().split(/\s+/).filter(Boolean)
  const visibleList = list.filter(p => searchTerms.every(term => normalizeSearch([p.title, p.label, p.family, p.catalog_code, ...(p.tags ?? []), fieldOf(p.slot, 'title', p.title), ...Object.values(p.brief), ...Object.values(edits[p.slot] ?? {}), groupConcepts([p])[0]?.name, 'id:' + p.slot, String(displayNumber(p.slot))].join(' ')).includes(term)) && (emojiFilter === 'all' || (emojiFilter === 'bookmarked' ? bookmarked(p) : emojiFilter === 'unmarked' ? !emojiOf(p) : emojiOf(p) === emojiFilter)) && matchesProgress(progress.get(bookmarkKey(p)), progressFilter))
  const chosen = picked === null ? list : list.filter(p => picked.includes(p.slot))
  const estimate = useQuery({ queryKey: ['estimate', project.id, project.provider, project.model, size, chosen.length], enabled: ready && chosen.length > 0,
    queryFn: () => request<{ total_usd: number | null; note: string }>(`${base}/generation-estimate?purpose=concept&count=${chosen.length}${size ? `&size=${encodeURIComponent(size)}` : ''}`), refetchInterval: 3000 })

  const builtIn = list.length > 0 && list[0].run === 0
  const generate = () => action.mutate(
    {
      path: `${base}/concepts/generate`,
      data: {
        ...(builtIn ? { slots: chosen.map(p => p.slot) } : { proposal_ids: chosen.map(p => p.id) }),
        confirmed, size: size || null, choices,
        // Only the edited slots travel; everything else keeps its stored wording.
        briefs: Object.fromEntries(chosen.filter(p => edits[p.slot]).map(p => [p.slot, Object.fromEntries(Object.entries(edits[p.slot]).filter(([field]) => field !== 'title'))])),
        titles: Object.fromEntries(chosen.filter(p => edits[p.slot]?.title).map(p => [p.slot, edits[p.slot].title])),
      },
    },
    { onSuccess: () => setSelectedRun(null) })

  const rerunImage = (concept: Concept, promptMode: 'saved' | 'current') => action.mutate({
    path: `${base}/concepts/${concept.id}/regenerate`,
    data: { size: size || null, prompt_mode: promptMode, ...(promptMode === 'current' ? { choices } : {}) },
  })

  const promptRerunButtons = (concept: Concept) => <>
    <Button size="sm" variant="outline" title="Giữ nguyên prompt đã dùng để tạo ảnh này" disabled={pending || active(concept.job) || !ready || !concept.job.prompt?.trim()} onClick={() => rerunImage(concept, 'saved')}>
      Tạo lại với prompt cũ
    </Button>
    <Button size="sm" variant="outline" title="Dùng mô tả mới nhất theo số concept và trang phục đang chọn" disabled={pending || active(concept.job) || !ready} onClick={() => rerunImage(concept, 'current')}>
      Tạo lại với prompt mới
    </Button>
  </>

  return <section className="space-y-5">
    {(bookmarks.error || bookmarkAction.error) && <ErrorAlert title="Không lưu được bookmark" error={bookmarkAction.error || bookmarks.error} />}
    <h2 className="text-xl font-semibold">Concept</h2>
    {concepts.isPending && <Skeleton className="h-64" />}
    {!!runs.length && <div className="flex flex-wrap items-center gap-4">
      <label>Đợt ảnh <select className="ml-2 rounded border p-2" aria-label="Đợt concept" value={run} onChange={e => { setSelectedRun(Number(e.target.value)); setRerunSelection(null); setRerunConfirmed(false) }}>
        {runs.map(n => <option key={n} value={n}>{n}</option>)}
      </select></label>
      <Button variant="outline" onClick={() => setCompact(!compact)}>{compact ? 'Xem thẻ chi tiết' : 'Xem bảng ảnh'}</Button>
      <a className="text-sm underline" href={apiUrl(`${base}/contact-sheet?run=${run}`)}>Tải bảng ảnh</a>
      <a className="text-sm underline" href={apiUrl(`${base}/concepts/download`)}>Tải toàn bộ concept (ZIP)</a>
      <span className="text-sm">{cards.filter(c => c?.job.status === 'succeeded').length}/{cards.length} hoàn tất</span>
    </div>}
    {!!runs.length && <div className="space-y-2 rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" variant="outline" onClick={() => pickForRerun(rerunSlots.length === slots.length ? [] : slots)}>
          {rerunSlots.length === slots.length ? 'Bỏ chọn cả đợt' : 'Chọn cả đợt'}
        </Button>
        <span className="text-sm">Đã chọn {rerunSlots.length}/{slots.length}</span>
        <Button size="sm" disabled={!ready || pending || !rerunSlots.length || (paid && !rerunConfirmed)} onClick={() => action.mutate({
          path: `${base}/concepts/generate`,
          data: { source_run: run, slots: rerunSlots, use_catalog_briefs: useCatalogBriefs, choices, size: size || null, confirmed: rerunConfirmed },
        }, { onSuccess: () => { setSelectedRun(null); setRerunSelection(null); setRerunConfirmed(false) } })}>Tạo lại concept đã chọn</Button>
      </div>
      <p className="text-xs text-muted-foreground">Tạo một đợt mới bằng model, kích thước và trang phục đang chọn.</p>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={useCatalogBriefs} onChange={e => { setUseCatalogBriefs(e.target.checked); setRerunConfirmed(false) }} /> Dùng mô tả mới từ catalog theo số concept</label>
      {paid && !!rerunSlots.length && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={rerunConfirmed} onChange={e => setRerunConfirmed(e.target.checked)} /> Xác nhận gửi {rerunSlots.length} ảnh tới nhà cung cấp có phí ({costLabel(unitPrice == null ? null : unitPrice * rerunSlots.length)})</label>}
    </div>}
    {!!runs.length && <div className={`grid gap-4 ${compact ? 'grid-cols-2 md:grid-cols-3 lg:grid-cols-5' : 'grid-cols-1'}`}>
      {cards.map(c => c ? <article key={c.id} className="min-w-0 self-start space-y-3 rounded-xl border p-4" aria-label={`Concept ${c.slot}`}>
        <label className="flex items-center gap-2 text-xs"><input type="checkbox" aria-label={`Chọn tạo lại ô ${c.slot}`} checked={rerunSlots.includes(c.slot)} onChange={e => pickForRerun(e.target.checked ? [...rerunSlots, c.slot] : rerunSlots.filter(slot => slot !== c.slot))} /> Chọn tạo lại</label>
        <div className={compact ? 'space-y-3' : 'grid gap-4 sm:grid-cols-[10rem_minmax(0,1fr)]'}>
          <div className="space-y-2">
        {c.job.output_asset_ids[0] ? <><ImagePreview assetId={c.job.output_asset_ids[0]} title={`Concept ${c.slot} · ${c.mood}`} /><DownloadLinks assetId={c.job.output_asset_ids[0]} /></> : active(c.job) ? <JobPlaceholder job={c.job} /> : <div className="flex aspect-[3/4] items-center justify-center rounded-lg bg-muted text-sm">Chưa có ảnh kết quả</div>}
          </div>
          <div className="min-w-0 space-y-3">
        <h3 className="font-semibold">{c.label || `${c.slot}. ${c.mood}`}</h3>
        {c.catalog_code && <p className="text-xs text-muted-foreground">{c.catalog_code} · Số {c.display_number ?? c.slot} · {c.family}</p>}
        <p className="break-words text-xs text-muted-foreground">{c.job.provider} · {c.job.model}{c.job.settings.size ? ` · ${c.job.settings.size}` : ''}</p>
        <p className="text-xs text-muted-foreground">Bản {c.revision}{c.job.meta?.master_outfit === true && ' · Trang phục nhân vật gốc'}</p>
        {c.job.meta?.full_body === true && <p className="text-xs text-muted-foreground">Khung toàn thân</p>}
        <CompactDescription key={c.id} text={c.camera} />
        {c.stale && <p className="text-sm text-amber-700">Dựa trên nhân vật gốc cũ</p>}

        {!compact && <>
          {c.brief.outfit && <p className="text-sm">Trang phục: {c.brief.outfit}</p>}
          <p className="text-sm">{c.brief.setting} · {c.brief.activity}</p>
          <details className="text-xs"><summary>Chi tiết concept và phiên bản trước</summary>
            <dl className="mt-2 space-y-1">{Object.entries(c.brief).filter(([, v]) => v).map(([k, v]) => <div key={k}><dt className="inline font-medium">{BRIEF_LABEL[k] ?? k}: </dt><dd className="inline">{v}</dd></div>)}</dl>
            {all.filter(p => p.slot === c.slot && p.id !== c.id).map(p => <div key={p.id} className="mt-3 border-t pt-3"><p>Bản {p.revision}</p>{p.job.output_asset_ids[0] && <><ImagePreview assetId={p.job.output_asset_ids[0]} title={`Concept ${p.slot} bản ${p.revision}`} /><Button size="sm" variant="outline" onClick={() => onEnhance(p.id)}>Nâng cấp bản {p.revision}</Button></>}<div className="my-2 flex flex-wrap gap-2">{promptRerunButtons(p)}</div><JobDetails job={p.job} projectId={project.id} /></div>)}
          </details>
          <JobDetails job={c.job} projectId={project.id} />
        </>}
        {!compact && ['failed', 'cancelled'].includes(c.job.status) &&
          <FixAndRetry concept={c} projectId={project.id} size={size} choices={choices} disabled={!ready} />}
        <div className="flex flex-wrap gap-2">
          <EditConceptPrompt key={c.id} concept={c} projectId={project.id} size={size} disabled={pending || active(c.job) || !ready} />
          {promptRerunButtons(c)}
          <Button size="sm" disabled={c.job.status !== 'succeeded'} onClick={() => onEnhance(c.id)}>Nâng cấp ô {c.slot}</Button>
        </div>
          </div>
        </div>
      </article> : null)}
    </div>}
    <PromptEditor projectId={project.id} name="concept" />
    <p className="text-sm text-muted-foreground">
      {list.length} concept lối sống với các bối cảnh, hoạt động và ánh sáng khác nhau.
      Chọn concept bạn muốn rồi tạo ảnh — không cần bước nào khác.
    </p>

    {!ready && <p className="text-sm">Xác nhận quyền sử dụng ảnh và duyệt nhân vật gốc để tiếp tục.</p>}

    {action.error && <ErrorAlert error={action.error} title="Thao tác không thành công" />}
    {proposals.error && <ErrorAlert error={proposals.error} title="Không tải được đề xuất" />}
    {concepts.error && <ErrorAlert error={concepts.error} title="Không tải được concept" />}
    {workflow.error && <ErrorAlert error={workflow.error} title="Không tải được nhân vật gốc" />}

    <CopyConceptConfiguration projectId={project.id} labels={BRIEF_LABEL} onCopy={next => {
      saveEdits(next)
      setPicked([])
      setConfirmed(false)
    }} />
    <OutfitSwitcher choices={choices} onChange={next => { setChoices(next); setConfirmed(false); setCustomConfirmed(false); setRerunConfirmed(false) }} />
    <Dialog open={historyKey !== null} onOpenChange={open => { if (!open) setHistoryKey(null) }}>
      <DialogContent className="max-h-[90vh] overflow-auto sm:max-w-3xl">
        <DialogTitle>Kết quả concept trong {project.name}</DialogTitle>
        <DialogDescription>Các đợt và phiên bản đã tạo trong dự án này.</DialogDescription>
        <div className="grid gap-4 sm:grid-cols-2">{(historyKey ? progress.get(historyKey)?.rows ?? [] : []).map(c => <div key={c.id} className="space-y-2 rounded-lg border p-3">
          <p className="text-sm">Đợt {c.run} · v{c.revision} · {c.job.status}</p>
          {c.job.output_asset_ids.map(id => <ImagePreview key={id} assetId={id} title={c.mood} />)}
          {c.job.error_message && <p className="text-sm text-destructive">{c.job.error_message}</p>}
        </div>)}</div>
      </DialogContent>
    </Dialog>
    <label className="flex items-center gap-2 text-sm">Trạng thái concept
      <select aria-label="Trạng thái concept" className="rounded border p-2" value={archiveFilter} onChange={e => {
        setArchiveFilter(e.target.value as ConceptArchiveFilter); setPicked([]); setConfirmed(false); setDetailSlot(null)
      }}>
        <option value="active">Đang dùng</option><option value="archived">Archived</option><option value="all">Tất cả</option>
      </select>
    </label>
    {archiveFilter !== 'active' && <p className="text-sm text-muted-foreground">Catalog bao gồm concept cũ đã được thay thế. Bạn vẫn có thể chọn chúng để tạo ảnh.</p>}
    {!proposals.isLoading && !list.length && archiveFilter === 'archived' && <p>Không có concept archived.</p>}
    {list.length > 0 && <details className="space-y-4 rounded-xl border p-4">
      <summary className="cursor-pointer font-semibold">{list.length} concept · Mở/đóng danh sách</summary>
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-semibold">{builtIn ? `${list.length} concept mặc định` : `Đề xuất đợt ${list[0].run}`}</h3>
        {!builtIn && <time className="text-sm text-muted-foreground" dateTime={list[0].created_at}>{new Date(list[0].created_at).toLocaleString('vi-VN')}</time>}
        <Button size="sm" variant="outline" onClick={() => setPicked(null)} disabled={picked === null}>Chọn tất cả</Button>
        <Button size="sm" variant="outline" onClick={() => { setPicked([]); setConfirmed(false) }} disabled={chosen.length === 0}>Bỏ chọn tất cả</Button>
        <span className="text-sm text-muted-foreground">Đang chọn {chosen.length}/{list.length}</span>
      </div>
      <div className="flex items-center gap-2">
        <label className="flex min-w-0 flex-1 items-center gap-2 text-sm">Tìm concept
          <input type="search" aria-label="Tìm concept" placeholder="Nhãn, tư thế, từ khóa hoặc mã C171…" value={conceptSearch} onChange={e => setConceptSearch(e.target.value)} className="min-w-0 flex-1 rounded-md border bg-background px-3 py-2" />
        </label>
        {conceptSearch && <Button size="sm" variant="outline" onClick={() => setConceptSearch('')}>Xóa tìm kiếm</Button>}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm">Gom nhóm theo <select aria-label="Gom nhóm concept" className="ml-2 rounded border p-2" value={groupMode} onChange={e => setGroupMode(e.target.value as 'family' | 'scene')}>
          <option value="family">Tư thế / hoạt động tương tự</option><option value="scene">Bối cảnh</option>
        </select></label>
        <label className="text-sm">Lọc concept <select aria-label="Lọc concept theo emoji" className="ml-2 rounded border p-2" value={emojiFilter} onChange={e => setEmojiFilter(e.target.value)}>
          <option value="all">Tất cả ({list.length})</option>
          <option value="bookmarked">🔖 Bookmark ({list.filter(bookmarked).length})</option>
          <option value="unmarked">Chưa đánh dấu ({list.filter(p => !emojiOf(p)).length})</option>
          {CONCEPT_EMOJIS.map(emoji => <option key={emoji} value={emoji}>{emoji} ({list.filter(p => emojiOf(p) === emoji).length})</option>)}
        </select></label>
        <label className="text-sm">Trong dự án này <select aria-label="Lọc trạng thái tạo concept" className="ml-2 rounded border p-2" value={progressFilter} onChange={e => setProgressFilter(e.target.value)}>
          <option value="all">Tất cả</option><option value="created">Đã có ảnh</option><option value="uncreated">Chưa tạo</option><option value="active">Đang tạo</option><option value="failed">Lỗi, chưa có ảnh</option>
        </select></label>
        <span className="text-xs text-muted-foreground">{list.filter(p => progress.get(bookmarkKey(p))?.imageIds.length).length}/{list.length} concept đã có ảnh trong dự án này.</span>
        <span className="text-xs text-muted-foreground">Hiện {visibleList.length}/{list.length} · Mã C giữ cố định khi đổi thứ tự nhóm; bookmark dùng chung giữa các dự án.</span>
        {(conceptSearch.trim() || emojiFilter !== 'all' || progressFilter !== 'all') && <Button size="sm" variant="outline" disabled={!visibleList.length} onClick={() => { setPicked(visibleList.map(p => p.slot)); setConfirmed(false) }}>Chỉ chọn các concept đang hiện</Button>}
      </div>
      {!visibleList.length && <p className="text-sm text-muted-foreground">Không có concept khớp bộ lọc.</p>}
      {groupConcepts(visibleList, groupMode).map(group => {
        const selectedCount = group.items.filter(p => picked === null || picked.includes(p.slot)).length
        return <section key={group.name} className="space-y-3 rounded-lg border p-3" aria-label={group.name}>
          <div className="flex flex-wrap items-center gap-3">
            <h4 className="font-semibold">{group.name}</h4>
            <span className="text-xs text-muted-foreground">{selectedCount}/{group.items.length} đã chọn</span>
            <Button size="sm" variant="outline" onClick={() => {
              const slots = group.items.map(p => p.slot)
              const current = picked ?? list.map(p => p.slot)
              setPicked(selectedCount === group.items.length ? current.filter(slot => !slots.includes(slot)) : [...new Set([...current, ...slots])])
              setConfirmed(false)
            }}>{selectedCount === group.items.length ? 'Bỏ chọn nhóm' : 'Chọn nhóm'}</Button>
          </div>
          <ul className="grid gap-3 grid-cols-2 md:grid-cols-3">
        {group.items.map((p, index) => <Fragment key={p.id}>
        {groupMode === 'scene' && p.family && p.family !== group.items[index - 1]?.family && <li className="col-span-full border-b pb-1 pt-2 text-xs font-semibold text-muted-foreground">{p.family} · {group.items.filter(item => item.family === p.family).length} biến thể</li>}
        <li className={`min-w-0 rounded-xl border p-3 text-sm ${picked !== null && !picked.includes(p.slot) ? 'opacity-60' : ''}`}>
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" aria-label={`Chọn concept ${displayNumber(p.slot)}`}
              checked={picked === null || picked.includes(p.slot)}
              onChange={e => {
                const current = picked ?? list.map(x => x.slot)
                const next = e.target.checked ? [...new Set([...current, p.slot])] : current.filter(slot => slot !== p.slot)
                setPicked(next.length === list.length ? null : next)
                setConfirmed(false)
              }} />Chọn
          </label>
          <div className="mt-2 flex flex-wrap items-center gap-2" data-concept-progress={p.slot}>
            <span className={progress.get(bookmarkKey(p))?.imageIds.length ? 'text-emerald-700 text-xs font-medium' : 'text-xs text-muted-foreground'}>{concepts.isPending ? 'Đang tải trạng thái…' : progressLabel(progress.get(bookmarkKey(p)))}</span>
            {!!progress.get(bookmarkKey(p))?.rows.length && <Button size="sm" variant="outline" onClick={() => setHistoryKey(bookmarkKey(p))}>Xem kết quả</Button>}
          </div>
          {!!progress.get(bookmarkKey(p))?.imageIds.length && <div className="mt-2 flex gap-1.5" aria-label="Ảnh đã tạo trong dự án này">
            {progress.get(bookmarkKey(p))!.imageIds.slice(0, 3).map((id, index) => <button key={id} type="button" className="relative min-w-0 flex-1 overflow-hidden rounded-md border" onClick={() => setHistoryKey(bookmarkKey(p))} aria-label={`Mở kết quả concept ${displayNumber(p.slot)}, ảnh ${index + 1}`}>
              <img src={assetUrl(id)} alt={`Ảnh đã tạo · ${p.title}`} loading="lazy" className="h-24 w-full bg-muted object-cover" />
              {index === 2 && progress.get(bookmarkKey(p))!.imageIds.length > 3 && <span className="absolute inset-0 flex items-center justify-center bg-black/50 font-semibold text-white">+{progress.get(bookmarkKey(p))!.imageIds.length - 3}</span>}
            </button>)}
          </div>}
          <button type="button" className="mt-2 rounded border px-2 py-1 text-xs" aria-label={`Bookmark concept ${displayNumber(p.slot)}`} aria-pressed={bookmarked(p)} disabled={bookmarkAction.isPending || !bookmarks.data} onClick={() => toggleBookmark(p)}>{bookmarked(p) ? '🔖 Đã lưu' : '🔖 Bookmark'}</button>
          <label className="mt-2 flex items-center gap-2 text-xs">Đánh dấu
            <select aria-label={`Emoji concept ${displayNumber(p.slot)}`} className="rounded border p-1 text-base" value={emojiOf(p)} onChange={e => markEmoji(p, e.target.value)}>
              <option value="">—</option>
              {CONCEPT_EMOJIS.map(emoji => <option key={emoji} value={emoji}>{emoji}</option>)}
            </select>
          </label>
          <button type="button" className="mt-2 w-full space-y-2 text-left" onClick={() => setDetailSlot(p.slot)} aria-label={`Xem chi tiết concept ${displayNumber(p.slot)}`}>
            {p.label && <span className="block font-semibold">{p.label}</span>}
            {isArchivedConcept(p) && <span className="block text-xs text-amber-700">Archived{p.replacement_slot ? ` · Thay thế bởi C${String(p.replacement_slot).padStart(3, '0')}` : ''}</span>}
            {p.catalog_code && <span className="block text-xs text-muted-foreground">{p.catalog_code} · Số {displayNumber(p.slot)}</span>}
            <span className="block font-semibold">{emojiOf(p) && `${emojiOf(p)} `}{displayNumber(p.slot)}. {fieldOf(p.slot, 'title', p.title)}</span>
            {/^full[- ]body\b/i.test(fieldOf(p.slot, 'framing', p.brief.framing ?? '')) && <span className="block text-xs text-muted-foreground">Khung toàn thân</span>}
            <span className="block line-clamp-2 text-xs text-muted-foreground">{fieldOf(p.slot, 'setting', p.brief.setting)}</span>
            <span className="block text-xs underline">Xem / sửa chi tiết{edits[p.slot] ? ' · đã sửa' : ''}</span>
          </button>
          {!!p.tags?.length && <div className="mt-2 flex flex-wrap gap-1" aria-label="Nhãn concept">{p.tags.map(tag => <span key={tag} className="rounded-full bg-muted px-2 py-0.5 text-[11px]">{tag}</span>)}</div>}
        </li></Fragment>)}
          </ul>
        </section>
      })}
    </details>}
    {list.length > 0 && <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-4 rounded-lg border p-4">
        <p className="text-sm">{costLabel(estimate.data ? estimate.data.total_usd : unitPrice == null ? null : unitPrice * chosen.length)} / {chosen.length} ảnh</p>
        {paid && <label className="text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> Xác nhận chi phí và gửi ảnh tới nhà cung cấp</label>}
        <Button disabled={pending || !ready || !chosen.length || (paid && !confirmed)} onClick={generate}>
          Tạo ảnh cho {chosen.length} concept
        </Button>
      </div>
      {estimate.data && <p className="text-xs text-muted-foreground">{estimate.data.note}</p>}
    </div>}

    {proposals.isPending && <Skeleton className="h-40" />}


    <details className="rounded-lg border p-4">
      <summary className="font-medium">Ảnh tùy chỉnh · tự chọn trang phục và bối cảnh</summary>
      <p className="mt-2 text-sm text-muted-foreground">
        Tạo ảnh riêng từ menu bên dưới, không liên quan tới các concept ở trên.
      </p>
      <div className="mt-3 space-y-3">
        <ConceptMenu projectId={project.id} choices={choices} onChange={value => { setChoices(value); setConfirmed(false); setCustomConfirmed(false); setRerunConfirmed(false) }} />
        {choices.outfit === 'master' && choices.scene === 'auto' && <p className="text-sm text-muted-foreground">Chọn bối cảnh cho ảnh dùng trang phục nhân vật gốc.</p>}
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
            || (choices.outfit === 'master' && choices.scene === 'auto')
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


    <Dialog open={detailSlot !== null} onOpenChange={open => { if (!open) setDetailSlot(null) }}>
      <DialogContent className="max-h-[90vh] overflow-auto sm:max-w-2xl">
        <DialogTitle>Chi tiết concept {detailSlot === null ? '' : displayNumber(detailSlot)}</DialogTitle>
        <DialogDescription>Xem và chỉnh mô tả trước khi tạo ảnh.</DialogDescription>
        {list.filter(p => p.slot === detailSlot).map(p => <div key={p.id} className="grid gap-3">
          <label className="grid gap-1 text-sm">Tiêu đề
            <input className="rounded border p-2" value={fieldOf(p.slot, 'title', p.title)} onChange={e => editField(p.slot, 'title', e.target.value)} />
          </label>
          {Object.entries(p.brief).filter(([field]) => choices.outfit !== 'master' || !WARDROBE_FIELDS.includes(field)).map(([field, value]) => <label key={field} className="grid gap-1 text-sm">{BRIEF_LABEL[field] ?? field}
            <input className="rounded border p-2" aria-label={`${BRIEF_LABEL[field] ?? field} của concept ${displayNumber(p.slot)}`}
              value={fieldOf(p.slot, field, value)} onChange={e => editField(p.slot, field, e.target.value)} />
          </label>)}
          <Button variant="outline" onClick={() => { const next = { ...edits }; delete next[p.slot]; saveEdits(next) }}>Hoàn tác về mặc định</Button>
        </div>)}
      </DialogContent>
    </Dialog>
  </section>
}
