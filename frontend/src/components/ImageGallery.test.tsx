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
  await user.click(screen.getByRole('button', { name: /Xem lớn:/ }))
  expect(screen.getByRole('dialog')).toBeInTheDocument()
  qc.clear()
})
