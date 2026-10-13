import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import CopyConceptConfiguration from './CopyConceptConfiguration'

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear() })

it('previews source edits and copies fields without starting a generation', async () => {
  localStorage.setItem('concept-edits:source', JSON.stringify({ 4: { outfit: 'custom outfit', gaze: 'slightly left' } }))
  const fetchMock = vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/configuration') ? { provider: 'mock', model: 'mock-v1', workflow_mode: 'manual', preset_name: null, preset_steps: {}, prompts: { concept: 'source prompt' } } : url.endsWith('/concept-proposals')
    ? [{ slot: 4, title: 'Poolside', brief: { outfit: 'original outfit', gaze: 'camera', setting: 'pool' } }]
    : [{ id: 'destination', name: 'Current project' }, { id: 'source', name: 'Source project' }]), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
  const onCopy = vi.fn()
  const user = userEvent.setup()
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <CopyConceptConfiguration projectId="destination" labels={{ outfit: 'Trang phục' }} onCopy={onCopy} />
  </QueryClientProvider>)
  await user.click(screen.getByText('Xem và chép cấu hình từ dự án khác'))
  await screen.findByRole('option', { name: 'Source project' })
  expect(screen.queryByRole('option', { name: 'Current project' })).toBeNull()
  await user.selectOptions(screen.getByLabelText('Dự án nguồn cho cấu hình concept'), 'source')
  await user.click(await screen.findByText('4. Poolside'))
  expect(screen.getByText('custom outfit')).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Chép toàn bộ cấu hình vào dự án này' }))
  await waitFor(() => expect(onCopy).toHaveBeenCalledWith({ 4: { title: 'Poolside', outfit: 'custom outfit', gaze: 'slightly left', setting: 'pool' } }))
  expect(fetchMock.mock.calls.map(([url]) => url)).toContain('/api/projects/source/concept-proposals')
  expect(fetchMock.mock.calls.map(([url]) => url).some(url => url.includes('/generate'))).toBe(false)
})
