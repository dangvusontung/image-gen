import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { GenerationJob } from '@/api/client'
import GenerationMonitor from './GenerationMonitor'

const job = (o: Partial<GenerationJob> & { id: string; status: string }): GenerationJob =>
  ({ purpose: 'master', provider: 'mock', model: 'mock-v1', output_asset_ids: [], reference_asset_ids: [],
     error_message: null, prompt: '', meta: {}, settings: {}, estimated_cost_usd: null, actual_cost_usd: null,
     attempts: 1, max_attempts: 3, cancel_requested: false, created_at: '', updated_at: '', ...o }) as GenerationJob

/** Each call to the jobs endpoint returns the next scripted poll. */
function serve(polls: GenerationJob[][]) {
  let call = 0
  const fetchMock = vi.fn().mockImplementation(() => {
    const body = polls[Math.min(call++, polls.length - 1)]
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
  })
  vi.stubGlobal('fetch', fetchMock)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <GenerationMonitor projectId="p1" />
    </QueryClientProvider>,
  )
  return () => qc.invalidateQueries({ queryKey: ['jobs', 'p1'] })
}

const panel = () => screen.queryByRole('region', { name: 'Tiến trình tạo ảnh' })

afterEach(() => vi.unstubAllGlobals())

describe('generation monitor', () => {
  it('stays hidden when nothing is generating', async () => {
    serve([[job({ id: 'old', status: 'succeeded' })]])
    await waitFor(() => expect(panel()).toBeNull())
  })

  it('lists what is running, with its purpose and status', async () => {
    serve([[job({ id: 'a', status: 'running' }), job({ id: 'b', status: 'queued', purpose: 'concept' })]])
    await waitFor(() => expect(panel()).toBeInTheDocument())
    expect(screen.getByText('Đang tạo 2 ảnh')).toBeInTheDocument()
    expect(screen.getByText('Nhân vật gốc')).toBeInTheDocument()
    expect(screen.getByText('Concept')).toBeInTheDocument()
    expect(screen.getByText('Đang tạo')).toBeInTheDocument()
    expect(screen.getByText('Đang chờ')).toBeInTheDocument()
  })

  it('announces a finish, including the error, and never announces the backlog', async () => {
    const refetch = serve([
      [job({ id: 'old', status: 'failed', error_message: 'cũ' })],
      [job({ id: 'old', status: 'failed', error_message: 'cũ' }), job({ id: 'new', status: 'running' })],
      [
        job({ id: 'old', status: 'failed', error_message: 'cũ' }),
        job({ id: 'new', status: 'failed', purpose: 'enhance', error_message: 'hết hạn mức' }),
      ],
    ])
    await waitFor(() => expect(panel()).toBeNull())
    refetch()
    await waitFor(() => expect(screen.getByText('Đang tạo 1 ảnh')).toBeInTheDocument())
    refetch()
    await waitFor(() => expect(screen.getByText(/Nâng cấp · Lỗi/)).toBeInTheDocument())
    expect(screen.getByText('hết hạn mức')).toBeInTheDocument()
    // The job that was already finished on arrival is never reported.
    expect(screen.queryByText('cũ')).toBeNull()
  })

  it('dismisses a finish note by hand, hiding the panel once empty', async () => {
    const refetch = serve([
      [],
      [job({ id: 'a', status: 'running' })],
      [job({ id: 'a', status: 'succeeded' })],
    ])
    await waitFor(() => expect(panel()).toBeNull())
    refetch()
    await waitFor(() => expect(panel()).toBeInTheDocument())
    refetch()
    await waitFor(() => expect(screen.getByText(/Nhân vật gốc · Hoàn tất/)).toBeInTheDocument())
    await userEvent.click(screen.getByRole('button', { name: 'Ẩn thông báo Nhân vật gốc' }))
    await waitFor(() => expect(panel()).toBeNull())
  })
})
