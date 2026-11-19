import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { ProjectDetail } from '@/api/client'
import ConceptsStep from './ConceptsStep'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })
it('loads archived catalog entries, labels them and clears hidden selections', async () => {
  const user = userEvent.setup()
  const active = { id: 'default-155', run: 0, slot: 155, title: 'Active pose', brief: {}, archived: false, display_number: 1 }
  const archived = { id: 'default-156', run: 0, slot: 156, title: 'Archived squat', brief: {}, archived: true, replacement_slot: 155, display_number: null }
  const fetchMock = vi.fn(async (url: string) => {
    if (url.includes('/prompts/')) return Response.json({ body: 'Concept prompt' })
    if (url.endsWith('/concept-options')) return Response.json(Object.fromEntries(['style', 'outfit', 'footwear', 'top', 'scene', 'lighting'].map(key => [key, [['auto', 'Auto']]])))
    if (url.endsWith('/workflow')) return Response.json({ approved_master_id: 'master' })
    if (url.includes('/concept-proposals?status=')) return Response.json([active, archived])
    if (url.endsWith('/concept-proposals')) return Response.json([active])
    if (url.endsWith('/concept-bookmarks')) return Response.json({ keys: [] })
    return Response.json([])
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <ConceptsStep project={{ id: 'p', provider: 'mock', model: 'mock-v1', rights_confirmed: true } as ProjectDetail} onEnhance={vi.fn()} />
  </QueryClientProvider>)
  await user.selectOptions(screen.getByLabelText('Trạng thái concept'), 'archived')
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url.endsWith('?status=archived'))).toBe(true))
  await screen.findByText(/Archived · Thay thế bởi C155/)
  await user.click(await screen.findByText('1 concept · Mở/đóng danh sách'))
  expect(await screen.findByRole('checkbox', { name: /Chọn concept/ })).toBeVisible()
  expect(screen.queryByText('Active pose')).not.toBeInTheDocument()
  expect(screen.getByText(/Archived · Thay thế bởi C155/)).toBeVisible()
  await user.click(screen.getByRole('checkbox', { name: /Chọn concept/ }))
  await user.selectOptions(screen.getByLabelText('Trạng thái concept'), 'all')
  await user.click(await screen.findByText('2 concept · Mở/đóng danh sách'))
  expect(await screen.findByText(/Active pose/)).toBeVisible()
  expect(screen.getByRole('button', { name: 'Tạo ảnh cho 0 concept' })).toBeDisabled()
})
