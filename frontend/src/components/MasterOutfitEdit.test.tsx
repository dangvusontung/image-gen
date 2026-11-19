import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { ProjectDetail } from '@/api/client'
import MasterOutfitEdit from './MasterOutfitEdit'

afterEach(() => vi.unstubAllGlobals())
it('uploads a pasted outfit and edits the existing Master only after confirmation', async () => {
  const user = userEvent.setup()
  const onClose = vi.fn()
  const calls: { url: string; init?: RequestInit }[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init })
    if (url.endsWith('/assets')) return Response.json([{ id: 'pasted', filename: 'outfit.png', kind: 'template', selected: true }])
    return Response.json({ job_ids: ['edited'] })
  }))
  const project = { id: 'p', rights_confirmed: true, assets: [{ id: 'reference', filename: 'face.png', kind: 'reference', selected: false }] } as ProjectDetail
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MasterOutfitEdit project={project} masterId="master" masterAssetId="source" onClose={onClose} />
  </QueryClientProvider>)
  const generate = screen.getByRole('button', { name: 'Tạo Master với outfit mới' })
  expect(generate).toBeDisabled()
  fireEvent.paste(screen.getByRole('region', { name: 'Đổi outfit Master' }), { clipboardData: { files: [new File(['image'], 'outfit.png', { type: 'image/png' })] } })
  await waitFor(() => expect(screen.getByAltText('Outfit được chọn')).toHaveAttribute('src', '/api/assets/pasted/content'))
  const upload = calls.find(call => call.url.endsWith('/assets'))!
  expect((upload.init?.body as FormData).get('kind')).toBe('template')
  expect(generate).toBeDisabled()
  expect(calls.some(call => call.url.endsWith('/outfit'))).toBe(false)
  await user.click(screen.getByRole('checkbox'))
  await user.click(generate)
  await waitFor(() => expect(onClose).toHaveBeenCalledOnce())
  const edit = calls.find(call => call.url.endsWith('/master/master/outfit'))!
  expect(JSON.parse(String(edit.init?.body))).toEqual({ outfit_reference_asset_id: 'pasted', confirmed: true })
  expect(calls.some(call => call.url.endsWith('/approve'))).toBe(false)
})
