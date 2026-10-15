import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import ImageGallery from './ImageGallery'

afterEach(() => vi.unstubAllGlobals())

it('filters the global gallery, resets pagination and opens images', async () => {
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    calls.push(url)
    const body = url.includes('/gallery?') ? { total: 50, items: [{ id: 'asset-1', project_id: 'p1', project_name: 'Alpha', purpose: 'concept', provider: 'mock', model: 'mock-v1', prompt: 'Example prompt', created_at: '2026-10-15T12:00:00Z' }] } : [{ id: 'p1', name: 'Alpha' }]
    return new Response(JSON.stringify(body), { status: 200 })
  }))
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={qc}><ImageGallery /></QueryClientProvider>)
  const user = userEvent.setup()
  await screen.findByText('50 ảnh')
  await user.click(screen.getByRole('button', { name: 'Trang sau' }))
  await waitFor(() => expect(calls.some(url => url.includes('offset=48'))).toBe(true))
  await user.selectOptions(screen.getByLabelText('Lọc gallery theo dự án'), 'p1')
  await waitFor(() => expect(calls.some(url => url.includes('project_id=p1') && url.includes('offset=0'))).toBe(true))
  await user.selectOptions(screen.getByLabelText('Lọc gallery theo loại ảnh'), 'concept')
  await waitFor(() => expect(calls.some(url => url.includes('purpose=concept') && url.includes('project_id=p1'))).toBe(true))
  expect(screen.queryByText('mock · mock-v1')).not.toBeInTheDocument()
  expect(screen.queryByText('Example prompt')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Xem chi tiết:/ }))
  expect(screen.getByRole('dialog')).toBeInTheDocument()
  expect(screen.getByText('Example prompt')).toBeInTheDocument()
  qc.clear()
})


it('downloads only explicitly checked images as a ZIP', async () => {
  let payload: unknown
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.includes('/gallery/download')) {
      payload = JSON.parse(init?.body as string)
      return new Response('zip bytes', { headers: { 'Content-Type': 'application/zip' } })
    }
    return new Response(JSON.stringify(url.includes('/gallery?') ? { total: 2, items: ['a', 'b'].map(id => ({ id, project_id: 'p1', project_name: 'Alpha', purpose: 'concept', provider: 'mock', model: 'mock-v1', prompt: 'hidden', created_at: '2026-10-15T12:00:00Z' })) } : []))
  }))
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:test'), revokeObjectURL: vi.fn() }))
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={qc}><ImageGallery projectId="p1" /></QueryClientProvider>)
  const user = userEvent.setup()
  await screen.findByText('2 ảnh')
  expect(screen.getByRole('button', { name: 'Tải 0 ảnh đã chọn (ZIP)' })).toBeDisabled()
  await user.click(screen.getAllByRole('button', { name: /Xem chi tiết:/ })[0])
  expect(screen.getByRole('dialog')).toHaveClass('h-[90dvh]')
  await user.click(screen.getByRole('button', { name: 'Ảnh sau' }))
  expect(screen.getByRole('dialog').querySelector('img')).toHaveAttribute('src', expect.stringContaining('/assets/b/content'))
  await user.keyboard('{ArrowLeft}')
  expect(screen.getByRole('dialog').querySelector('img')).toHaveAttribute('src', expect.stringContaining('/assets/a/content'))
  await user.keyboard('{Escape}')
  await user.click(screen.getByRole('checkbox', { name: 'Chọn ảnh b' }))
  await user.click(screen.getByRole('button', { name: 'Tải 1 ảnh đã chọn (ZIP)' }))
  await waitFor(() => expect(payload).toEqual({ asset_ids: ['b'] }))
  await waitFor(() => expect(click).toHaveBeenCalledOnce())
  click.mockRestore()
  qc.clear()
})
