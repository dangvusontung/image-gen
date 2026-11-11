import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDownToLine, ArrowLeft, ArrowRight, Check, ChevronDown, CircleHelp, Layers3, LoaderCircle, Plus, RefreshCw, Send, Settings2, Sparkles, Sticker, WandSparkles, X } from 'lucide-react'
import { assetUrl, request, useProjects, useProviders } from '@/api/client'
import DialogueEditor from './DialogueEditor'
import ReferenceInput from './ReferenceInput'
import ConceptStep from './ConceptStep'
import ModelPicker from './ModelPicker'
import { activeJob, freshJob, json, packRequest, previewUrl, type Estimate, type Pack, type PackSummary, type StickerItem } from './api'

const STYLES = [
  { id: 'chibi', name: 'Chibi', emoji: '🌻', description: 'Small body, big feelings' },
  { id: 'clay', name: '3D clay', emoji: '🍡', description: 'Soft, squishy & playful' },
  { id: 'comic', name: 'Comic', emoji: '💥', description: 'Bold lines, bold reactions' },
  { id: 'kawaii', name: 'Kawaii', emoji: '🍑', description: 'A little extra adorable' },
]
const money = (amount: number | null) => amount == null ? 'Price unavailable' : amount === 0 ? 'Free' : `~$${amount.toFixed(3)}`

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => { const dialog = ref.current; dialog?.showModal(); return () => dialog?.close() }, [])
  return <dialog ref={ref} className="ss-dialog" aria-label={title} onCancel={e => { e.preventDefault(); onClose() }}>
    <div className="ss-dialog-title"><h2>{title}</h2><button className="ss-icon-button" aria-label="Close dialog" onClick={onClose}><X size={20} /></button></div>{children}
  </dialog>
}

export default function StickerStudio() {
  const query = useQueryClient()
  const [packId, setPackId] = useState(() => window.location.hash.slice(1))
  const [create, setCreate] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState<StickerItem | null>(null)
  const [confirmIds, setConfirmIds] = useState<string[] | null>(null)
  const [help, setHelp] = useState(false)
  const [previewTheme, setPreviewTheme] = useState('light')
  const [name, setName] = useState('')
  const [publisher, setPublisher] = useState('')
  const packs = useQuery({ queryKey: ['sticker-packs'], queryFn: () => packRequest<PackSummary[]>() })
  const packQuery = useQuery({
    queryKey: ['sticker-pack', packId], enabled: !!packId,
    queryFn: () => packRequest<Pack>(`/${packId}`),
    refetchInterval: q => [...Object.values(q.state.data?.jobs ?? {}), ...(q.state.data?.concepts ?? []).map(c => c.job)].some(activeJob) ? 1500 : false,
  })
  const pack = packQuery.data
  const providers = useProviders()
  const busy = [...Object.values(pack?.jobs ?? {}), ...(pack?.concepts ?? []).map(c => c.job)].some(activeJob)
  const openPack = (id: string) => { window.location.hash = id; setPackId(id); setError('') }
  useEffect(() => {
    const change = () => { setPackId(window.location.hash.slice(1)); setError('') }
    window.addEventListener('hashchange', change)
    return () => window.removeEventListener('hashchange', change)
  }, [])
  useEffect(() => {
    setSelected(new Set(pack?.items.map(i => i.id) ?? []))
    setName(pack?.name ?? ''); setPublisher(pack?.publisher ?? '')
  }, [pack?.id, pack?.name, pack?.publisher]) // Polling must not reset selections or text edits.

  async function refresh() {
    await Promise.all([query.invalidateQueries({ queryKey: ['sticker-pack', packId] }), query.invalidateQueries({ queryKey: ['sticker-packs'] })])
  }
  const mutate = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => { setError(''); return action() },
    onSuccess: refresh, onError: e => setError(e.message),
  })
  const save = (changes: Partial<Pick<Pack, 'name' | 'publisher' | 'style' | 'items' | 'concept_brief'>>) => {
    if (!pack) return Promise.reject(new Error('Open a pack first'))
    return packRequest<Pack>(`/${pack.id}`, json('PUT', { name: pack.name, publisher: pack.publisher, style: pack.style, concept_brief: pack.concept_brief, items: pack.items, ...changes }))
  }
  const provider = providers.data?.find(p => p.name === pack?.project.provider)
  const ready = pack?.items.filter(i => freshJob(pack, i)) ?? []
  const selectedReady = ready.filter(i => selected.has(i.id))
  const selectedIds = pack?.items.filter(i => selected.has(i.id)).map(i => i.id) ?? []
  const locked = busy || mutate.isPending
  const [exporting, setExporting] = useState(false)
  async function download(platform: 'whatsapp' | 'telegram') {
    if (!pack) return
    setError(''); setExporting(true)
    try {
      const blob = await request<Blob>(`/sticker-packs/${pack.id}/export`, json('POST', { platform, item_ids: selectedReady.map(i => i.id) }), 'blob')
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href = url; link.download = `${platform}-stickers.zip`; link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) { setError((e as Error).message) } finally { setExporting(false) }
  }

  return <div className="ss-app">
    <header className="ss-topbar">
      <a className="ss-brand" href="/stickers.html"><span className="ss-logo"><Sticker size={23} /></span>sticker<span>studio</span><span className="ss-beta">BETA</span></a>
      <nav><a href="/" className="ss-core-link"><Layers3 size={15} /> Character Studio <ArrowRight size={14} /></a><button className="ss-help" onClick={() => setHelp(true)}><CircleHelp size={17} /> How it works</button></nav>
    </header>

    <div className="ss-layout">
      <aside className="ss-sidebar">
        <div className="ss-sidebar-heading"><span>YOUR WORKSPACE</span><span className="ss-local-dot">Local</span></div>
        <button className="ss-primary ss-full" onClick={() => setCreate(true)}><Plus size={17} /> New sticker pack</button>
        <div className="ss-section-label">MY PACKS <span>{packs.data?.length ?? 0}</span></div>
        {packs.isPending && <p className="ss-muted">Loading your packs…</p>}
        {packs.error && <p role="alert" className="ss-small-error">{packs.error.message}</p>}
        <div className="ss-pack-list">{packs.data?.map(p => <button key={p.id} className={`ss-pack-link ${packId === p.id ? 'is-active' : ''}`} onClick={() => openPack(p.id)}>
          <span className="ss-pack-thumb">{p.reference_id ? <img src={assetUrl(p.reference_id)} alt="" /> : <Sticker size={21} />}</span>
          <span><strong>{p.name}</strong><small>{p.count} stickers · {STYLES.find(s => s.id === p.style)?.name}</small></span><ChevronDown size={14} />
        </button>)}</div>
        {!packs.isPending && !packs.data?.length && <div className="ss-empty-library"><Sticker size={24} /><p>A home for all your<br />little expressions.</p></div>}
        <div className="ss-sidebar-bottom"><div className="ss-tip-art">✦ <span>☺</span> ✧</div><strong>Your character.<br />A thousand moods.</strong><p>Make something that feels<br />a little more you.</p><span className="ss-core-badge"><span /> Powered by your image core</span></div>
      </aside>

      <main className="ss-main">
        {!packId && <div className="ss-welcome">
          <span className="ss-eyebrow"><Sparkles size={14} /> SMALL STICKERS. BIG PERSONALITY.</span>
          <h1>Every mood,<br /><em>uniquely you.</em></h1><p>Turn a photo or your favorite character into a whole<br className="ss-desktop-break" /> pack of expressive stickers. Made for your chats.</p>
          <button className="ss-primary ss-large" onClick={() => setCreate(true)}><WandSparkles size={19} /> Make your first pack <ArrowRight size={17} /></button>
          <div className="ss-demo-row" aria-label="Example sticker expressions"><div>👋<span>Hey, you!</span></div><div>🥹<span>All the feels</span></div><div>🥳<span>Let's go!</span></div><div>😴<span>BRB, dreaming</span></div></div>
          <div className="ss-welcome-features"><span><Check size={15} /> Your photos & characters</span><span><Check size={15} /> Transparent backgrounds</span><span><Check size={15} /> WhatsApp & Telegram</span></div>
          <p className="ss-demo-note">Expression ideas shown above. Your stickers are generated from your own reference.</p>
        </div>}

        {packId && packQuery.isPending && <div className="ss-loading"><LoaderCircle className="ss-spin" /> Opening your pack…</div>}
        {packQuery.error && <div className="ss-error" role="alert">{packQuery.error.message}<button onClick={() => openPack('')}>Back to workspace</button></div>}
        {pack && <>
          <div className="ss-page-heading"><div><div className="ss-breadcrumb">YOUR WORKSPACE <span>/</span> STICKER BUILDER</div><h1>{pack.name} <span className="ss-count-pill">{pack.items.length} stickers</span></h1><p>A little character. A whole lot of personality.</p></div><button className="ss-secondary" onClick={() => setCreate(true)}><Plus size={16} /> New pack</button></div>
          <div className="ss-progress"><span className={pack.project.assets.length ? 'is-done' : 'is-current'}><b>1</b> Photo</span><i /><span className={pack.approved_concept ? 'is-done' : 'is-current'}><b>{pack.approved_concept ? <Check size={13} /> : '2'}</b> Approve look</span><i /><span className={ready.length ? 'is-done' : pack.approved_concept ? 'is-current' : ''}><b>3</b> Expressions</span><i /><span className={ready.length ? 'is-current' : ''}><b>4</b> Export</span></div>

          {error && <div className="ss-error" role="alert">{error}<button aria-label="Dismiss error" onClick={() => setError('')}><X size={16} /></button></div>}
          <div className="ss-editor-layout">
            <section className="ss-settings">
              <div className="ss-panel-title"><span><Settings2 size={17} /> Pack setup</span><small>01</small></div>
              <div className="ss-setting-section"><h3>Your character</h3><p>The familiar face behind every sticker.</p><ReferenceInput pack={pack} disabled={locked} onChange={refresh} onError={setError} />
                <label className="ss-checkbox-label"><input type="checkbox" checked={pack.project.rights_confirmed} disabled={locked} onChange={e => mutate.mutate(() => request(`/projects/${pack.id}`, json('PATCH', { rights_confirmed: e.target.checked })))} /> I have permission to use these images.</label>
              </div>
              <div className="ss-setting-section"><h3>Pick a personality</h3><p>One consistent style, across your pack.</p><div className="ss-style-grid">{STYLES.map(s => <button key={s.id} title={s.description} aria-pressed={pack.style === s.id} className={`ss-style ${pack.style === s.id ? 'is-selected' : ''}`} disabled={locked} onClick={() => mutate.mutate(() => save({ style: s.id }))}><span>{s.emoji}</span><strong>{s.name}</strong>{pack.style === s.id && <Check size={12} />}</button>)}</div></div>
              <div className="ss-setting-section"><h3>Pack details</h3><label className="ss-field">Pack name<input value={name} maxLength={128} disabled={locked} onChange={e => setName(e.target.value)} onBlur={() => { if (name.trim() && name !== pack.name) mutate.mutate(() => save({ name })) }} /></label><label className="ss-field">Made by<input value={publisher} maxLength={128} disabled={locked} onChange={e => setPublisher(e.target.value)} onBlur={() => { if (publisher.trim() && publisher !== pack.publisher) mutate.mutate(() => save({ publisher })) }} /></label></div>
              <ModelPicker project={pack.project} onChange={refresh} />
            </section>

            <div className="ss-canvas-column">
              <ConceptStep key={pack.id} pack={pack} disabled={locked} onChange={refresh} onError={setError} />
              {!pack.approved_concept && <p className="ss-concept-lock">Approve your character’s look above to unlock sticker expressions.</p>}
              <section className="ss-canvas">
                <div className="ss-canvas-heading"><div><h2>A mood for every moment <span>✧</span></h2><p>Edit an expression, add a caption, make it yours.</p></div><span className="ss-ready-count"><span /> {ready.length} / {pack.items.length} ready</span></div>
                <div className="ss-toolbar"><label className="ss-checkbox-label"><input aria-label="Select all stickers" type="checkbox" checked={pack.items.every(i => selected.has(i.id))} onChange={e => setSelected(new Set(e.target.checked ? pack.items.map(i => i.id) : []))} />{selected.size} selected</label><div className="ss-preview-controls"><span>Preview on</span>{['light', 'dark', 'check'].map(t => <button key={t} title={`${t} background`} aria-label={`${t} background`} aria-pressed={previewTheme === t} className={`ss-swatch ss-swatch-${t} ${previewTheme === t ? 'is-selected' : ''}`} onClick={() => setPreviewTheme(t)} />)}</div></div>
                <div className={`ss-sticker-grid ss-theme-${previewTheme}`}>{pack.items.map((item, index) => <StickerCard key={item.id} pack={pack} item={item} index={index} checked={selected.has(item.id)} disabled={locked || !pack.approved_concept} onCheck={() => setSelected(old => { const next = new Set(old); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next })} onEdit={() => setEditing({ ...item })} onGenerate={() => setConfirmIds([item.id])} onCancel={() => mutate.mutate(() => request(`/jobs/${pack.jobs[item.id].id}/cancel`, { method: 'POST' }))} />)}</div>
                <div className="ss-canvas-footer"><span><Sparkles size={15} /> Same character. A fresh expression every time.</span><button className="ss-text-button" disabled={locked || !pack.approved_concept || pack.items.length >= 30} onClick={() => setEditing({ id: `custom-${Date.now()}`, expression: '', caption: '', emoji: '✨' })}><Plus size={15} /> Add expression</button></div>
              </section>
              <div className="ss-generate-bar"><div><strong>{busy ? 'A little magic is happening…' : !pack.approved_concept ? 'Approve your character concept first.' : 'Ready to bring them to life?'}</strong><p>{busy ? 'You can leave this page. Your jobs keep running on the backend.' : `${selectedIds.length} expressions · 512 × 512 px · transparent backgrounds`}</p></div><button className="ss-primary" disabled={locked || !pack.approved_concept || !selectedIds.length || !pack.project.assets.length || !pack.project.rights_confirmed || !provider?.enabled} onClick={() => setConfirmIds(selectedIds)}>{busy ? <LoaderCircle size={18} className="ss-spin" /> : <WandSparkles size={18} />} {busy ? 'Generating stickers' : `Generate ${selectedIds.length} sticker${selectedIds.length === 1 ? '' : 's'}`}</button></div>
              <section className="ss-export"><div className="ss-export-heading"><div className="ss-export-icon"><ArrowDownToLine size={21} /></div><div><h2>From your studio to your chats.</h2><p>Export {selectedReady.length} selected, finished sticker{selectedReady.length === 1 ? '' : 's'}. Import instructions included.</p></div></div><div className="ss-export-actions"><button disabled={exporting || selectedReady.length < 3} onClick={() => download('whatsapp')}><span className="ss-whatsapp">◉</span><span><strong>WhatsApp</strong><small>WebP pack · 3–30 stickers</small></span><ArrowDownToLine size={17} /></button><button disabled={exporting || !selectedReady.length} onClick={() => download('telegram')}><Send size={25} className="ss-telegram" /><span><strong>Telegram</strong><small>WebP pack · publish via @Stickers</small></span><ArrowDownToLine size={17} /></button></div><p className="ss-export-note">WhatsApp: import files through a sticker-maker app. Telegram: upload files to @Stickers. Exports do not publish automatically.</p></section>
            </div>
          </div>
        </>}
        <footer className="ss-footer"><span>Made for the way you say things.</span><span>Sticker Studio <span>✦</span> Local-first, always yours.</span></footer>
      </main>
    </div>

    {create && <CreatePack onClose={() => setCreate(false)} onCreated={id => { setCreate(false); openPack(id); query.invalidateQueries({ queryKey: ['sticker-packs'] }) }} />}
    {editing && pack && <Modal title={pack.items.some(i => i.id === editing.id) ? 'A little more expression' : 'Add a new expression'} onClose={() => setEditing(null)}><form onSubmit={e => { e.preventDefault(); const next = pack.items.some(i => i.id === editing.id) ? pack.items.map(i => i.id === editing.id ? editing : i) : [...pack.items, editing]; mutate.mutate(async () => { await save({ items: next }); setSelected(s => new Set([...s, editing.id])); setEditing(null) }) }}><DialogueEditor pack={pack} item={editing} onChange={setEditing} /><label className="ss-field">Emoji tag<input required value={editing.emoji} maxLength={16} onChange={e => setEditing({ ...editing, emoji: e.target.value })} /></label><p className="ss-muted">Your text is combined with the character locally for previews and exports.</p>{mutate.error && <p role="alert" className="ss-small-error">{mutate.error.message}</p>}<div className="ss-dialog-actions">{pack.items.some(i => i.id === editing.id) && pack.items.length > 1 && <button type="button" className="ss-text-button" disabled={locked} onClick={() => mutate.mutate(async () => { await save({ items: pack.items.filter(i => i.id !== editing.id) }); setSelected(s => new Set([...s].filter(id => id !== editing.id))); setEditing(null) })}>Remove expression</button>}<button className="ss-primary" disabled={locked || !editing.expression.trim()}>Save expression <Check size={16} /></button></div></form></Modal>}
    {confirmIds && pack && <GenerateDialog pack={pack} ids={confirmIds} onClose={() => setConfirmIds(null)} onGenerated={() => { setConfirmIds(null); refresh() }} />}
    {help && <Modal title="From a face to a feeling" onClose={() => setHelp(false)}><div className="ss-help-content"><p><b>1. Bring your character.</b> Upload or paste a photo, choose a style, describe the character’s look, then generate and approve a concept. That image becomes the reference for every sticker. Confirm you have permission to use the photos.</p><p><b>2. Make it expressive.</b> Choose a style and edit the poses, captions, and emoji tags. Select a configured model, review the estimate, and generate. Mock mode creates labeled placeholders for free.</p><p><b>3. Take it to your chats.</b> Choose finished stickers and download a platform ZIP. WhatsApp needs 3–30 stickers, a sticker-maker app or native app integration. For Telegram, extract the files and publish through <a href="https://t.me/Stickers" target="_blank" rel="noreferrer">@Stickers</a>.</p><p>Images are centered on a transparent 512 × 512 canvas. Solid magenta backgrounds are removed automatically. If the model misses the background instructions, regenerate that sticker. Dialogue uses real fonts and stays editable. Character consistency and cutout quality depend on the model; inspect your pack before sharing.</p><p><a href="https://github.com/WhatsApp/stickers" target="_blank" rel="noreferrer">WhatsApp sticker requirements ↗</a> · <a href="https://core.telegram.org/stickers" target="_blank" rel="noreferrer">Telegram sticker requirements ↗</a></p></div></Modal>}
  </div>
}

function StickerCard({ pack, item, index, checked, disabled, onCheck, onEdit, onGenerate, onCancel }: { pack: Pack; item: StickerItem; index: number; checked: boolean; disabled: boolean; onCheck: () => void; onEdit: () => void; onGenerate: () => void; onCancel: () => void }) {
  const job = pack.jobs[item.id]
  const active = activeJob(job)
  const fresh = freshJob(pack, item)
  const [imageError, setImageError] = useState(false)
  useEffect(() => setImageError(false), [job?.id, JSON.stringify(item)])
  return <article className={`ss-sticker-card ${checked ? 'is-checked' : ''}`}>
    <div className="ss-card-top"><label title={`Select ${item.id}`}><input type="checkbox" aria-label={`Select sticker ${index + 1}`} checked={checked} onChange={onCheck} /></label><span>{String(index + 1).padStart(2, '0')}</span>{fresh && !imageError && <Check size={14} className="ss-card-check" />}</div>
    <button className="ss-art" disabled={disabled} onClick={onEdit} aria-label={`Edit sticker ${index + 1}`}>
      {fresh && !imageError ? <img src={previewUrl(pack, item)} alt={item.expression} onError={() => setImageError(true)} /> : active ? <div className="ss-art-loading"><LoaderCircle className="ss-spin" size={30} /><span>{job.status === 'queued' ? 'In the queue' : 'Making magic…'}</span></div> : <div className={`ss-expression-placeholder ss-expression-${index % 4}`}><span>{item.emoji}</span><small>{item.caption || item.id}</small></div>}
    </button>
    <div className="ss-card-bottom"><button onClick={onEdit} disabled={disabled} title={item.expression}>{item.caption || item.id.replaceAll('-', ' ')} <span>↗</span></button><button className="ss-icon-button" aria-label={`Generate sticker ${index + 1}`} title="Generate this sticker" disabled={disabled || !pack.project.assets.length} onClick={onGenerate}><RefreshCw size={13} /></button></div>
    {job?.status === 'failed' && <p className="ss-card-error" title={job.error_message ?? ''}>Generation failed. Retry ↗</p>}
    {job?.status === 'cancelled' && <p className="ss-card-notice">Cancelled · ready to retry</p>}
    {imageError && <p className="ss-card-error">Preview failed · edit text or retry</p>}
    {!fresh && job?.status === 'succeeded' && <p className="ss-card-notice">Artwork changed or legacy lettering · regenerate</p>}
    {active && <button className="ss-cancel-job" onClick={onCancel}>Cancel</button>}
    {!job && <span className="ss-card-draft">EXPRESSION IDEA</span>}
  </article>
}

function CreatePack({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const projects = useProjects()
  const [name, setName] = useState('My everyday moods')
  const [source, setSource] = useState('')
  const [rights, setRights] = useState(false)
  const create = useMutation({ mutationFn: () => packRequest<Pack>('', json('POST', { name, rights_confirmed: rights, source_project_id: source || null })), onSuccess: p => onCreated(p.id) })
  return <Modal title="A new pack of possibilities" onClose={onClose}><form onSubmit={e => { e.preventDefault(); create.mutate() }}><p className="ss-muted">Start with a photo, or give a familiar character some new moods.</p><label className="ss-field">Pack name<input autoFocus required maxLength={128} value={name} onChange={e => setName(e.target.value)} /></label><label className="ss-field">Start with<select value={source} onChange={e => setSource(e.target.value)}><option value="">A photo I’ll upload</option>{projects.data?.map(p => <option key={p.id} value={p.id}>{p.name} · approved character</option>)}</select></label><p className="ss-muted">Character Studio sources need an approved master. A private copy is saved with this pack.</p><label className="ss-checkbox-label"><input type="checkbox" checked={rights} onChange={e => setRights(e.target.checked)} /> I have permission to use these photos or characters.</label>{create.error && <p className="ss-small-error" role="alert">{create.error.message}</p>}<div className="ss-dialog-actions"><button type="button" className="ss-secondary" onClick={onClose}><ArrowLeft size={15} /> Back</button><button className="ss-primary" disabled={create.isPending || !name.trim() || !rights}>{create.isPending ? <LoaderCircle size={16} className="ss-spin" /> : <Plus size={16} />} Create pack</button></div></form></Modal>
}

function GenerateDialog({ pack, ids, onClose, onGenerated }: { pack: Pack; ids: string[]; onClose: () => void; onGenerated: () => void }) {
  const estimate = useQuery({ queryKey: ['sticker-estimate', pack.id, pack.project.provider, pack.project.model, ids.length, pack.project.assets.map(a => a.id).join(',')], queryFn: () => packRequest<Estimate>(`/${pack.id}/estimate?count=${ids.length}`) })
  const generate = useMutation({ mutationFn: () => packRequest(`/${pack.id}/generate`, json('POST', { item_ids: ids, confirmed: true, size: estimate.data?.size })), onSuccess: onGenerated })
  return <Modal title="Let’s make some expressions" onClose={() => { if (!generate.isPending) onClose() }}><p className="ss-muted">Generate {ids.length} individual sticker{ids.length === 1 ? '' : 's'} from your reference. Previous results stay in the generation history.</p><div className="ss-estimate"><span>{pack.project.provider} / {pack.project.model}</span><strong>{estimate.isPending ? 'Calculating…' : estimate.data ? money(estimate.data.total_usd) : 'Estimate unavailable'}</strong><small>{ids.length} images · square · {estimate.data?.size ?? 'default size'}</small></div><p className="ss-muted">{pack.project.provider === 'mock' ? 'Mock mode creates labeled placeholders to try the workflow. Choose a configured provider for real AI stickers.' : 'Your references will be sent to this provider. This is an estimate; input tokens and final provider billing may differ. Unavailable pricing does not mean free generation.'}</p>{(estimate.error || generate.error) && <p className="ss-small-error" role="alert">{(estimate.error || generate.error)?.message}</p>}<div className="ss-dialog-actions"><button className="ss-secondary" disabled={generate.isPending} onClick={onClose}>Keep editing</button><button className="ss-primary" disabled={!estimate.data || generate.isPending} onClick={() => generate.mutate()}>{generate.isPending ? <LoaderCircle className="ss-spin" size={17} /> : <WandSparkles size={17} />} {generate.isPending ? 'Starting…' : 'Confirm & generate'}</button></div></Modal>
}
