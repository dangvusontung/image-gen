import { useEffect, useState } from 'react'
import { Check, LoaderCircle, WandSparkles } from 'lucide-react'
import { assetUrl, request } from '@/api/client'
import { activeJob, json, packRequest, type Estimate, type Pack } from './api'

export default function ConceptStep({ pack, disabled, onChange, onError }: {
  pack: Pack; disabled: boolean; onChange: () => Promise<void>; onError: (message: string) => void
}) {
  const [brief, setBrief] = useState(pack.concept_brief)
  const [variants, setVariants] = useState(2)
  const [estimate, setEstimate] = useState<Estimate | null>(null)
  const [pending, setPending] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  useEffect(() => { setBrief(pack.concept_brief); setEstimate(null) }, [pack.id, pack.concept_brief, pack.style, pack.project.provider, pack.project.model])
  useEffect(() => setEstimate(null), [pack.project.assets.map(asset => `${asset.id}:${asset.selected}`).join(',')])
  const approved = pack.approved_concept
  const changed = brief.trim() !== pack.concept_brief
  const locked = disabled || pending
  const candidates = showHistory || !approved ? pack.concepts : pack.concepts.filter(c => c.job.id === approved.id)
  async function perform(action: () => Promise<unknown>) {
    setPending(true); onError('')
    try { await action(); await onChange() } catch (error) { onError((error as Error).message) }
    finally { setPending(false) }
  }
  async function saveBrief() {
    await packRequest(`/${pack.id}`, json('PUT', { name: pack.name, publisher: pack.publisher, style: pack.style, concept_brief: brief.trim(), items: pack.items }))
  }
  return <section className="ss-concept-panel">
    <div className="ss-concept-heading"><div><span className="ss-eyebrow">FIRST, MEET YOUR CHARACTER</span><h2>Create a look you love.</h2><p>Generate a character concept, then approve one look for every sticker.</p></div><span className={`ss-concept-status ${approved ? 'is-approved' : ''}`}>{approved ? <><Check size={13} /> Look approved</> : 'Approval needed'}</span></div>
    <label className="ss-field">Character concept brief <small>Describe the look, outfit, colors or personality you want.</small><textarea aria-label="Character concept brief" value={brief} disabled={locked} maxLength={2000} placeholder="Keep my glasses and hairstyle. A cozy oversized hoodie, soft rounded proportions, warm colors…" onChange={event => { setBrief(event.target.value); setEstimate(null) }} /></label>
    <div className="ss-concept-actions"><label>Options <select aria-label="Concept variants" value={variants} disabled={locked} onChange={event => { setVariants(Number(event.target.value)); setEstimate(null) }}>{[1, 2, 3, 4].map(n => <option key={n} value={n}>{n} look{n === 1 ? '' : 's'}</option>)}</select></label>
      {changed && <button className="ss-secondary" disabled={locked} onClick={() => void perform(saveBrief)}>Save concept brief</button>}
      <button className="ss-primary" disabled={locked || changed || !pack.project.rights_confirmed || !pack.project.assets.length} onClick={() => void perform(async () => { const result = await packRequest<Estimate>(`/${pack.id}/estimate?purpose=concept&count=${variants}`); setEstimate(result) })}>{pack.concepts.some(c => activeJob(c.job)) ? <LoaderCircle className="ss-spin" size={16} /> : <WandSparkles size={16} />} {pack.concepts.some(c => activeJob(c.job)) ? 'Creating your looks…' : pack.concepts.length ? 'Generate more concepts' : 'Generate character concepts'}</button>
    </div>
    {changed && <p className="ss-muted">Save your brief before generating. Changing the brief requires approving a new concept.</p>}
    {estimate && <div className="ss-concept-confirm"><div><strong>{estimate.total_usd == null ? 'Price unavailable' : estimate.total_usd === 0 ? 'Free · offline previews' : `Estimated $${estimate.total_usd.toFixed(3)}`}</strong><p>{variants} concept images · {pack.project.provider} / {pack.project.model}. {pack.project.provider === 'mock' ? 'Mock creates labeled placeholders.' : 'References are sent to this provider; final billing may differ.'}</p></div><button className="ss-secondary" disabled={pending} onClick={() => setEstimate(null)}>Cancel</button><button className="ss-primary" disabled={locked} onClick={() => void perform(async () => { await packRequest(`/${pack.id}/concepts/generate`, json('POST', { variants, confirmed: true, size: estimate.size })); setEstimate(null) })}>Confirm concept generation</button></div>}
    {!pack.project.assets.length && <p className="ss-muted">Start by uploading or pasting a character photo in Pack setup.</p>}
    <div className="ss-concept-grid">{candidates.map(({ job, current }, index) => <article key={job.id} className={approved?.id === job.id ? 'is-approved' : ''}>
      <div className="ss-concept-art">{job.status === 'succeeded' && job.output_asset_ids[0] ? <a href={assetUrl(job.output_asset_ids[0])} target="_blank" rel="noreferrer" title="Open full-size character concept"><img src={assetUrl(job.output_asset_ids[0])} alt={`Character concept ${index + 1}`} /></a> : activeJob(job) ? <div><LoaderCircle size={25} className="ss-spin" /><span>{job.status === 'queued' ? 'Queued' : 'Creating a new look…'}</span></div> : <p>{job.error_message || 'Generation cancelled. Try creating another concept.'}</p>}</div>
      <div className="ss-concept-card-footer"><span>Look {pack.concepts.findIndex(c => c.job.id === job.id) + 1}{!current && job.status === 'succeeded' ? ' · previous setup' : ''}</span><button className={approved?.id === job.id ? 'ss-secondary' : 'ss-primary'} disabled={locked || !current || approved?.id === job.id} onClick={() => void perform(() => packRequest(`/${pack.id}/concepts/${job.id}/approve`, { method: 'POST' }))}>{approved?.id === job.id ? <><Check size={13} /> Approved look</> : 'Approve this look'}</button></div>
      {activeJob(job) && <button className="ss-cancel-job" disabled={pending} onClick={() => void perform(() => request(`/jobs/${job.id}/cancel`, { method: 'POST' }))}>Cancel generation</button>}
    </article>)}</div>
    {approved && pack.concepts.length > 1 && <button className="ss-text-button" onClick={() => setShowHistory(!showHistory)}>{showHistory ? 'Show approved look only' : 'Review other concepts'}</button>}
    <p className="ss-concept-note">{approved ? 'Your approved concept is the identity reference for sticker generation. Choosing another look marks existing sticker artwork for regeneration.' : 'Sticker generation unlocks after you approve a finished concept. Dialogue stays editable and is added separately.'}</p>
  </section>
}
