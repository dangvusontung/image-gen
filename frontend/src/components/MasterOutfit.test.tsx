import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { ProjectDetail } from '@/api/client'
import CharacterStep from './CharacterStep'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })
const project = {
  id: 'outfit-project', provider: 'mock', model: 'mock-v1', rights_confirmed: true,
  assets: [
    { id: 'face', filename: 'face.png', selected: true, kind: 'reference' },
    { id: 'dress', filename: 'dress.png', selected: true, kind: 'reference' },
    { id: 'template', filename: 'template.png', selected: false, kind: 'template' },
    { id: 'off', filename: 'off.png', selected: false, kind: 'reference' },
  ],
} as ProjectDetail
function mount() {
  const mutations: Record<string, unknown>[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') { mutations.push(JSON.parse(String(init.body))); return Response.json({ job_ids: ['job'] }) }
    if (url.endsWith('/master/outfit-options')) return Response.json({ outfit: [['bikini', 'Bikini']] })
    if (url.endsWith('/workflow')) return Response.json({ masters: [], turnarounds: [], approvals: [], approved_master_id: null })
    if (url.includes('/generation-estimate')) return Response.json({ total_usd: null, note: 'Estimate' })
    return Response.json([])
  }))
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><CharacterStep project={project} step="master" /></QueryClientProvider>)
  return mutations
}

it('previews the outfit source and sends it only after confirmation', async () => {
  const user = userEvent.setup()
  const mutations = mount()
  await user.click(screen.getByRole('button', { name: 'Lấy trang phục từ dress.png' }))
  expect(screen.getByAltText('Ảnh nguồn trang phục Master')).toHaveAttribute('src', '/api/assets/dress/content')
  expect(screen.queryByRole('button', { name: 'Lấy trang phục từ off.png' })).not.toBeInTheDocument()
  const generate = screen.getByRole('button', { name: 'Tạo nhân vật gốc' })
  expect(generate).toBeDisabled()
  await user.click(screen.getByRole('checkbox', { name: /Tôi xác nhận tạo 1 ảnh/ }))
  await user.click(generate)
  await waitFor(() => expect(mutations[0]).toMatchObject({ variants: 1, outfit_reference_asset_id: 'dress' }))
  expect(localStorage.getItem('master-outfit:outfit-project')).toBe('dress')
})

it('blocks a deselected saved source until it is replaced or cleared', async () => {
  const user = userEvent.setup()
  localStorage.setItem('master-outfit:outfit-project', 'off')
  mount()
  expect(screen.getByRole('alert')).toHaveTextContent('Ảnh outfit không còn được chọn')
  const generate = screen.getByRole('button', { name: 'Tạo nhân vật gốc' })
  expect(generate).toBeDisabled()
  await user.click(screen.getByRole('button', { name: 'Theo cấu hình Master' }))
  await waitFor(() => expect(generate).toBeEnabled())
})


it('switches from an uploaded template to a preset without sending both sources', async () => {
  const user = userEvent.setup()
  const mutations = mount()
  await user.click(screen.getByRole('button', { name: 'Lấy trang phục từ template.png' }))
  expect(screen.getByAltText('Ảnh nguồn trang phục Master')).toHaveAttribute('src', '/api/assets/template/content')
  await waitFor(() => expect(screen.getByLabelText('Outfit Master có sẵn')).toBeEnabled())
  await user.selectOptions(screen.getByLabelText('Outfit Master có sẵn'), 'bikini')
  expect(screen.queryByAltText('Ảnh nguồn trang phục Master')).not.toBeInTheDocument()
  await user.click(screen.getByRole('checkbox', { name: /Tôi xác nhận tạo 1 ảnh/ }))
  await user.click(screen.getByRole('button', { name: 'Tạo nhân vật gốc' }))
  await waitFor(() => expect(mutations[0]).toMatchObject({ master_outfit: { outfit: 'bikini' } }))
  expect(mutations[0]).not.toHaveProperty('outfit_reference_asset_id')
})
