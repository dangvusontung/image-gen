import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { request } from '@/api/client'
import ReferenceInput from './ReferenceInput'
import type { Pack } from './api'

vi.mock('@/api/client', () => ({ request: vi.fn(), assetUrl: (id: string) => `/assets/${id}` }))
const pack = { id: 'pack', project: { rights_confirmed: true, assets: [] } } as unknown as Pack
const onChange = vi.fn().mockResolvedValue(undefined)
const onError = vi.fn()
beforeEach(() => { vi.mocked(request).mockReset().mockResolvedValue([]); onChange.mockClear(); onError.mockClear() })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function pasteImage(target: Document | HTMLElement = document) {
  const file = new File(['image bytes'], 'clipboard.png', { type: 'image/png' })
  const event = new Event('paste', { bubbles: true, cancelable: true })
  Object.defineProperty(event, 'clipboardData', { value: { items: [{ kind: 'file', getAsFile: () => file }], files: [file] } })
  fireEvent(target, event)
  return event
}

it('uploads clipboard images through the shared asset API and refreshes the pack', async () => {
  render(<ReferenceInput pack={pack} disabled={false} onChange={onChange} onError={onError} />)
  expect(pasteImage().defaultPrevented).toBe(true)
  await waitFor(() => expect(onChange).toHaveBeenCalledOnce())
  const [path, init] = vi.mocked(request).mock.calls[0]
  expect(path).toBe('/projects/pack/assets')
  expect((init?.body as FormData).getAll('files')).toHaveLength(1)
})

it('leaves paste in dialogue inputs alone', () => {
  render(<><textarea aria-label="Dialogue" /><ReferenceInput pack={pack} disabled={false} onChange={onChange} onError={onError} /></>)
  expect(pasteImage(screen.getByLabelText('Dialogue')).defaultPrevented).toBe(false)
  expect(request).not.toHaveBeenCalled()
})

it('requires confirmed photo rights for pasted images', () => {
  const restricted = { ...pack, project: { ...pack.project, rights_confirmed: false } }
  render(<ReferenceInput pack={restricted} disabled={false} onChange={onChange} onError={onError} />)
  pasteImage()
  expect(request).not.toHaveBeenCalled()
  expect(onError).toHaveBeenCalledWith(expect.stringContaining('Confirm permission'))
  expect(screen.getByRole('button', { name: 'Paste image' })).toBeDisabled()
})

it('reads clipboard images only when the paste button is clicked', async () => {
  const read = vi.fn().mockResolvedValue([{ types: ['image/png'], getType: async () => new Blob(['image'], { type: 'image/png' }) }])
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { read } })
  render(<ReferenceInput pack={pack} disabled={false} onChange={onChange} onError={onError} />)
  expect(read).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Paste image' }))
  await waitFor(() => expect(onChange).toHaveBeenCalledOnce())
  expect(read).toHaveBeenCalledOnce()
})

it('offers the paste shortcut when clipboard permission is denied', async () => {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { read: vi.fn().mockRejectedValue(new Error('denied')) } })
  render(<ReferenceInput pack={pack} disabled={false} onChange={onChange} onError={onError} />)
  fireEvent.click(screen.getByRole('button', { name: 'Paste image' }))
  await waitFor(() => expect(onError).toHaveBeenCalledWith(expect.stringContaining('Ctrl/Cmd+V')))
  expect(request).not.toHaveBeenCalled()
})
