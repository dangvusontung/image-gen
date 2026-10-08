import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ProjectDetail } from '@/api/client'
import ReferencesStep from './ReferencesStep'

const baseProject: ProjectDetail = {
  id: 'p1',
  name: 'Test',
  description: null,
  rights_confirmed: false,
  provider: 'mock',
  model: 'mock-v1',
  created_at: '2026-10-08T00:00:00Z',
  updated_at: '2026-10-08T00:00:00Z',
  assets: [],
}

const asset = (id: string, position: number) => ({
  id,
  kind: 'reference' as const,
  filename: `${id}.png`,
  size: 2048,
  content_type: 'image/png',
  width: 10,
  height: 10,
  position,
  created_at: '2026-10-08T00:00:00Z',
})

function renderStep(project: ProjectDetail) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ReferencesStep project={project} />
    </QueryClientProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('ReferencesStep', () => {
  it('disables upload until rights are confirmed, then PATCHes the project', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...baseProject, rights_confirmed: true }), { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderStep(baseProject)

    const inputs = document.querySelectorAll<HTMLInputElement>('input[type=file]')
    expect(inputs).toHaveLength(2)
    inputs.forEach((i) => expect(i).toBeDisabled())
    expect(screen.getByText(/xác nhận quyền sử dụng ảnh ở trên/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('checkbox'))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/projects/p1')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body)).toEqual({ rights_confirmed: true })
  })

  it('shows few-photos warning and sends new order on move', async () => {
    const project = { ...baseProject, rights_confirmed: true, assets: [asset('a', 0), asset('b', 1)] }
    const fetchMock = vi.fn().mockResolvedValue(new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    renderStep(project)

    expect(screen.getByText('Ít ảnh tham chiếu')).toBeInTheDocument()
    expect(screen.getAllByRole('img')).toHaveLength(2)

    await userEvent.click(screen.getAllByRole('button', { name: 'Chuyển ra sau' })[0])
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/projects/p1/assets/order')
    expect(JSON.parse(init.body)).toEqual({ asset_ids: ['b', 'a'] })
  })

  it('surfaces server error messages', async () => {
    const project = { ...baseProject, rights_confirmed: true }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: { code: 'invalid_image', message: 'x.png: File không phải ảnh hợp lệ' } }), {
          status: 400,
        }),
      ),
    )
    renderStep(project)
    const input = document.querySelectorAll<HTMLInputElement>('input[type=file]')[0]
    await userEvent.upload(input, new File(['x'], 'x.png', { type: 'image/png' }))
    expect(await screen.findByText(/File không phải ảnh hợp lệ/)).toBeInTheDocument()
  })
})
