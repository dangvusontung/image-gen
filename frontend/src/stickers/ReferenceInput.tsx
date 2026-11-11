import { useEffect, useRef, useState } from 'react'
import { ClipboardPaste, ImagePlus, LoaderCircle, X } from 'lucide-react'
import { assetUrl, request } from '@/api/client'
import { ACCEPTED_TYPES, LIMITS, MAX_FILE_BYTES } from '@/lib/upload'
import type { Pack } from './api'

export default function ReferenceInput({ pack, disabled, onChange, onError }: {
  pack: Pack; disabled: boolean; onChange: () => Promise<void>; onError: (message: string) => void
}) {
  const [uploading, setUploading] = useState(false)
  const [reading, setReading] = useState(false)
  const inFlight = useRef(false)
  const clipboardInFlight = useRef(false)
  const blocked = disabled || uploading || reading || !pack.project.rights_confirmed

  async function upload(files: File[]) {
    if (!files.length || disabled || inFlight.current) return
    if (!pack.project.rights_confirmed) { onError('Confirm permission below before adding images.'); return }
    if (files.some(f => !ACCEPTED_TYPES.includes(f.type))) { onError('Use a PNG, JPEG or WebP image.'); return }
    if (files.some(f => f.size > MAX_FILE_BYTES)) { onError('Each reference image must be 20 MB or smaller.'); return }
    const existing = pack.project.assets.filter(a => a.kind === 'reference').length
    if (existing + files.length > LIMITS.reference) { onError(`A pack can have up to ${LIMITS.reference} reference photos. Remove a photo before adding more.`); return }
    inFlight.current = true; setUploading(true); onError('')
    const form = new FormData()
    files.forEach(file => form.append('files', file)); form.append('kind', 'reference')
    try { await request(`/projects/${pack.id}/assets`, { method: 'POST', body: form }); await onChange() }
    catch (error) { onError((error as Error).message) }
    finally { inFlight.current = false; setUploading(false) }
  }

  useEffect(() => {
    function paste(event: ClipboardEvent) {
      const target = event.target instanceof Element ? event.target : document.activeElement
      // Keep ordinary text paste in dialogue fields and other editors untouched.
      if (target?.closest('input, textarea, [contenteditable]:not([contenteditable="false"])') || document.querySelector('dialog[open]')) return
      const clipboard = event.clipboardData
      if (!clipboard || disabled || inFlight.current || clipboardInFlight.current) return
      const items = Array.from(clipboard.items ?? []).filter(item => item.kind === 'file')
      const files = items.length ? items.map(item => item.getAsFile()).filter((file): file is File => !!file) : Array.from(clipboard.files ?? [])
      const images = files.filter(file => file.type.startsWith('image/'))
      if (!images.length) return
      event.preventDefault()
      void upload(images)
    }
    document.addEventListener('paste', paste)
    return () => document.removeEventListener('paste', paste)
  })

  async function readClipboard() {
    if (blocked || inFlight.current || clipboardInFlight.current) return
    if (!navigator.clipboard?.read) { onError('Click the page and press Ctrl/Cmd+V to paste an image.'); return }
    clipboardInFlight.current = true; setReading(true)
    try {
      const items = await navigator.clipboard.read()
      const files: File[] = []
      for (const [index, item] of items.entries()) {
        const type = item.types.find(t => ACCEPTED_TYPES.includes(t))
        if (!type) continue
        const blob = await item.getType(type)
        files.push(new File([blob], `clipboard-${Date.now()}-${index + 1}.${type === 'image/jpeg' ? 'jpg' : type.split('/')[1]}`, { type }))
      }
      if (!files.length) { onError('No image found in the clipboard. Copy an image first, then paste it here.'); return }
      await upload(files)
    } catch { onError('Clipboard access was unavailable. Click the page and press Ctrl/Cmd+V to paste your copied image.'); }
    finally { clipboardInFlight.current = false; setReading(false) }
  }

  return <>
    <div className="ss-reference-list">{pack.project.assets.map(asset => <div key={asset.id} className="ss-reference">
      <img src={assetUrl(asset.id)} alt={asset.filename} />
      <button className="ss-reference-remove" disabled={disabled || uploading} aria-label={`Remove ${asset.filename}`} onClick={async () => {
        try { await request(`/assets/${asset.id}`, { method: 'DELETE' }); await onChange() }
        catch (error) { onError((error as Error).message) }
      }}><X size={12} /></button>
    </div>)}</div>
    <label className={`ss-upload ${blocked ? 'is-disabled' : ''}`}>
      <input type="file" accept="image/png,image/jpeg,image/webp" multiple aria-label="Upload reference photos" disabled={blocked} onChange={event => { void upload(Array.from(event.target.files ?? [])); event.target.value = '' }} />
      {uploading ? <LoaderCircle className="ss-spin" size={22} /> : <ImagePlus size={23} />}
      <strong>{uploading ? 'Uploading…' : pack.project.assets.length ? 'Add reference photos' : 'Choose a character photo'}</strong>
      <span>{pack.project.rights_confirmed ? 'Choose photos · JPG, PNG, WebP' : 'Confirm permission below to upload'}</span>
    </label>
    <button type="button" className="ss-secondary ss-paste-image" disabled={blocked} onClick={() => void readClipboard()}><ClipboardPaste size={14} /> Paste image</button>
    <p className="ss-clipboard-hint">Or copy an image and press Ctrl/Cmd+V on this page.</p>
  </>
}
