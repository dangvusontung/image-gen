import { useEffect, useRef, useState } from 'react'
import { LoaderCircle, Move, Sparkles } from 'lucide-react'
import { request } from '@/api/client'
import { freshJob, json, type Pack, type StickerItem } from './api'

export function suggestReaction(dialogue: string): string {
  const words = dialogue.toLocaleLowerCase().normalize('NFC')
  const matches: [RegExp, string][] = [
    [/hết cứu|facepalm|oh no|trời ơi/, 'Facepalming with eyes closed and exaggerated frustration'],
    [/thiệt|thật|really|what|ủa|hả|\?/, 'Confused, one eyebrow raised, pointing at themselves with a questioning expression'],
    [/love|yêu|thương|nhớ/, 'Warm affectionate smile, hugging a heart close to their chest'],
    [/thank|cảm ơn|cám ơn/, 'Grateful smile, hands pressed together and a small appreciative bow'],
    [/haha|lol|cười|😂/, 'Laughing uncontrollably, eyes squeezed shut, tears of joy'],
    [/nope|không|đừng|stop/, 'Firmly shaking their head with arms crossed in a playful refusal'],
    [/sleep|ngủ|mệt|zzz|tired/, 'Sleepy half-closed eyes, yawning and hugging a pillow'],
    [/yay|yes|đỉnh|tuyệt|hoan hô|chúc/, 'Celebrating with both arms raised, a huge smile and confetti'],
    [/hi\b|hello|chào/, 'Waving hello enthusiastically with a big friendly smile'],
    [/sorry|xin lỗi|buồn|sad/, 'Apologetic puppy eyes, shoulders lowered and hands held together'],
  ]
  return matches.find(([pattern]) => pattern.test(words))?.[1] ?? 'Speaking expressively with a lively face and one hand gesturing toward the viewer'
}

export default function DialogueEditor({ pack, item, onChange }: { pack: Pack; item: StickerItem; onChange: (item: StickerItem) => void }) {
  const [preview, setPreview] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const area = useRef<HTMLDivElement>(null)
  const saved = pack.items.find(i => i.id === item.id)
  const canPreview = !!saved && freshJob(pack, saved)
  const payload = JSON.stringify(item)
  useEffect(() => {
    if (!canPreview) return
    const controller = new AbortController()
    let url = ''
    const timer = window.setTimeout(async () => {
      setLoading(true); setError('')
      try {
        const blob = await request<Blob>(`/sticker-packs/${pack.id}/stickers/${item.id}/preview`, { ...json('POST', JSON.parse(payload)), signal: controller.signal }, 'blob')
        if (controller.signal.aborted) return
        url = URL.createObjectURL(blob); setPreview(url)
      } catch (e) { if (!controller.signal.aborted) setError((e as Error).message) }
      finally { if (!controller.signal.aborted) setLoading(false) }
    }, 180)
    return () => { window.clearTimeout(timer); controller.abort(); if (url) URL.revokeObjectURL(url) }
  }, [payload, canPreview, pack.id, item.id])

  function move(event: React.PointerEvent) {
    const rect = area.current?.getBoundingClientRect()
    if (!rect) return
    const clamp = (v: number) => Math.round(Math.max(0, Math.min(1, v)) * 1000) / 1000
    onChange({ ...item, text_x: clamp((event.clientX - rect.left) / rect.width), text_y: clamp((event.clientY - rect.top) / rect.height) })
  }

  return <div className="ss-dialogue-editor">
    <label className="ss-field">What they say <small>Caption · rendered exactly with real fonts</small>
      <textarea aria-label="What they say" value={item.caption} maxLength={120} rows={2} placeholder="Type their words here…" onChange={e => onChange({ ...item, caption: e.target.value })} />
    </label>
    <div className="ss-dialogue-privacy">Your dialogue stays out of the image prompt. Change it anytime without paying for new artwork.</div>
    <div className="ss-text-styles" role="group" aria-label="Text presentation">
      {(['caption', 'speech', 'thought'] as const).map(style => <button type="button" key={style} aria-pressed={(item.text_style ?? 'caption') === style} onClick={() => onChange({ ...item, text_style: style, text_y: style === 'caption' ? .84 : .18 })}>{style === 'caption' ? 'Outlined caption' : style === 'speech' ? 'Speech bubble' : 'Thought bubble'}</button>)}
    </div>
    <div className="ss-text-options"><label className="ss-field">Text size<input aria-label="Text size" type="range" min="24" max="64" value={item.text_size ?? 48} onChange={e => onChange({ ...item, text_size: Number(e.target.value) })} /></label><label className="ss-field">Text color<input aria-label="Text color" type="color" value={item.text_color ?? '#302a3b'} onChange={e => onChange({ ...item, text_color: e.target.value })} /></label></div>
    {canPreview ? <>
      <div ref={area} className="ss-dialogue-preview" aria-label="Sticker text preview">
        {preview && <img src={preview} alt="Sticker with your dialogue" />}
        {loading && <span className="ss-dialogue-loading"><LoaderCircle size={16} className="ss-spin" /></span>}
        {!!item.caption.trim() && <button type="button" className="ss-text-handle" aria-label="Drag text position" style={{ left: `${(item.text_x ?? .5) * 100}%`, top: `${(item.text_y ?? .84) * 100}%` }} onPointerDown={e => { e.currentTarget.setPointerCapture(e.pointerId); move(e) }} onPointerMove={e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) move(e) }} onKeyDown={e => { const offsets: Record<string, [number, number]> = { ArrowLeft: [-.02, 0], ArrowRight: [.02, 0], ArrowUp: [0, -.02], ArrowDown: [0, .02] }; const delta = offsets[e.key]; if (delta) { e.preventDefault(); onChange({ ...item, text_x: Math.max(0, Math.min(1, (item.text_x ?? .5) + delta[0])), text_y: Math.max(0, Math.min(1, (item.text_y ?? .84) + delta[1])) }) } }}><Move size={17} /></button>}
      </div><p className="ss-muted">Drag the move handle to position the text, or use its arrow keys. Long dialogue wraps and shrinks automatically.</p>
    </> : <p className="ss-muted">Generate the artwork once to preview your text on the character. Older stickers with AI lettering need one regeneration.</p>}
    {error && <p className="ss-small-error" role="alert">{error}</p>}
    <div className="ss-reaction-heading"><label htmlFor="sticker-reaction">How they react</label><button type="button" className="ss-text-button" disabled={!item.caption.trim()} onClick={() => onChange({ ...item, expression: suggestReaction(item.caption) })}><Sparkles size={13} /> Suggest reaction</button></div>
    <label className="ss-field"><textarea id="sticker-reaction" aria-label="How they react" required maxLength={500} value={item.expression} onChange={e => onChange({ ...item, expression: e.target.value })} placeholder="A cheeky wink with finger guns…" /></label>
    <p className="ss-muted">Reaction suggestions are local presets you can edit. Changing the reaction needs new artwork; changing dialogue, layout or emoji does not.</p>
  </div>
}
