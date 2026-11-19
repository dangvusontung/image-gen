import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { ProjectDetail } from '@/api/client'
import ConceptsStep from './ConceptsStep'

afterEach(() => {
  localStorage.clear()
  vi.unstubAllGlobals()
})

it.each([0, 1])('uses master clothing for generation, custom scenes and regeneration (proposal run %s)', async run => {
  const user = userEvent.setup()
  const mutations: { url: string; body: unknown }[] = []
  const brief = { setting: 'a garden', outfit: 'a red dress', pose: 'standing', framing: 'full-body vertical portrait' }
  const concept = {
    id: 'c1', run: 1, slot: 1, revision: 1, mood: 'Garden', camera: 'front', brief,
    job: { status: 'succeeded', prompt: 'saved prompt', provider: 'mock', model: 'mock-v1', settings: {}, meta: run === 0 ? { master_outfit: true } : undefined, output_asset_ids: [] },
  }
  const auto = [['auto', 'Theo concept']]
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') {
      mutations.push({ url, body: JSON.parse(String(init.body)) })
      return Response.json({ job_ids: ['j1'] })
    }
    if (url.includes('/prompts/concept?')) return Response.json({ body: 'Concept prompt' })
    if (url.endsWith('/workflow')) return Response.json({ approved_master_id: 'm1' })
    if (url.endsWith('/concepts')) return Response.json([concept])
    if (url.endsWith('/concept-proposals')) return Response.json([{ id: 'p1', run, slot: 1, title: 'Garden', brief }])
    if (url.endsWith('/concept-options')) return Response.json({
      outfit: [...auto, ['bikini', 'Bikini'], ['master', 'Giữ trang phục nhân vật gốc']],
      footwear: [...auto, ['barefoot', 'Chân trần']],
      scene: [...auto, ['garden', 'Vườn hoa']],
      top: auto, style: auto, lighting: auto,
    })
    if (url.endsWith('/concept-bookmarks')) return Response.json({ keys: [] })
    return Response.json([])
  })
  vi.stubGlobal('fetch', fetchMock)
  const project = { id: 'p1', provider: 'mock', model: 'mock-v1', rights_confirmed: true } as ProjectDetail
  render(<QueryClientProvider client={new QueryClient()}>
    <ConceptsStep project={project} onEnhance={vi.fn()} />
  </QueryClientProvider>)

  await user.selectOptions(screen.getByLabelText('Đổi trang phục concept'), 'master')
  expect(screen.getByLabelText('Đổi giày concept')).toBeDisabled()
  expect(await screen.findByText(run === 0 ? 'Bản 1 · Trang phục nhân vật gốc' : 'Bản 1')).toBeInTheDocument()

  await user.click(await screen.findByText('1 concept · Mở/đóng danh sách'))
  expect(await screen.findByText('Khung toàn thân')).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Chọn tất cả' }))
  const generate = screen.getByRole('button', { name: 'Tạo ảnh cho 1 concept' })
  await waitFor(() => expect(generate).toBeEnabled())
  await user.click(generate)
  await waitFor(() => expect(mutations[0]).toMatchObject({
    url: '/api/projects/p1/concepts/generate',
    body: { ...(run === 0 ? { slots: [1] } : { proposal_ids: ['p1'] }), choices: { outfit: 'master' } },
  }))

  await user.click(screen.getByText('Ảnh tùy chỉnh · tự chọn trang phục và bối cảnh'))
  const custom = screen.getByRole('button', { name: 'Tạo 1 ảnh tùy chỉnh' })
  expect(custom).toBeDisabled()
  expect(screen.getByLabelText('Giày concept')).toBeDisabled()
  const menu = screen.getByRole('group', { name: 'Chọn trang phục và bối cảnh' })
  await user.click(within(menu).getByRole('checkbox', { name: 'Dùng khung toàn thân' }))
  await user.selectOptions(screen.getByLabelText('Bối cảnh concept'), 'garden')
  expect(custom).toBeEnabled()
  await user.click(custom)
  await waitFor(() => expect(mutations[1]).toMatchObject({
    url: '/api/projects/p1/concepts/generate',
    body: { custom: true, choices: { outfit: 'master', scene: 'garden', full_body: true } },
  }))

  await user.click(screen.getByRole('button', { name: 'Tạo lại với prompt mới' }))
  await waitFor(() => expect(mutations[2]).toMatchObject({
    url: '/api/projects/p1/concepts/c1/regenerate',
    body: { prompt_mode: 'current', choices: { outfit: 'master', full_body: true } },
  }))
})
