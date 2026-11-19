import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { ProjectDetail } from '@/api/client'
import CloneConcept from './CloneConcept'

afterEach(() => vi.unstubAllGlobals())
it('clones from an explicitly chosen Master and pasted reference with a per-run outfit choice', async () => {
  const user = userEvent.setup()
  const payloads: unknown[] = []
  const onQueued = vi.fn()
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/workflow')) return Response.json({ approved_master_id: 'approved', masters: [
      { id: 'approved', round: 1, variant: 1, job: { status: 'succeeded', output_asset_ids: ['master-photo'] } },
      { id: 'other', round: 2, variant: 1, job: { status: 'succeeded', output_asset_ids: ['other-photo'] } },
    ] })
    if (url.endsWith('/assets')) return Response.json([{ id: 'pasted', filename: 'scene.png', kind: 'template' }])
    if (init?.method === 'POST') payloads.push(JSON.parse(String(init.body)))
    return Response.json({ job_ids: ['job'], concept_ids: ['clone'] })
  }))
  const project = { id: 'p', rights_confirmed: true, assets: [] } as unknown as ProjectDetail
  render(<QueryClientProvider client={new QueryClient()}><CloneConcept project={project} onQueued={onQueued} /></QueryClientProvider>)
  await user.click(screen.getByText('Clone concept từ ảnh'))
  await waitFor(() => expect(screen.getByLabelText('Master để clone concept')).toHaveValue('approved'))
  await user.selectOptions(screen.getByLabelText('Master để clone concept'), 'other')
  fireEvent.paste(screen.getByText(/Master giữ nhận diện/).parentElement!, { clipboardData: { files: [new File(['image'], 'scene.png', { type: 'image/png' })] } })
  await waitFor(() => expect(screen.getByAltText('Refer clone')).toHaveAttribute('src', '/api/assets/pasted/content'))
  expect(screen.getByAltText('Master clone')).toHaveAttribute('src', '/api/assets/other-photo/content')
  const generate = screen.getByRole('button', { name: 'Tạo clone concept' })
  expect(generate).toBeDisabled()
  await user.click(screen.getByRole('checkbox', { name: /Giữ outfit Master/ }))
  await user.click(screen.getByRole('checkbox', { name: /Xác nhận tạo 1 concept/ }))
  await user.click(generate)
  await waitFor(() => expect(onQueued).toHaveBeenCalledWith('clone'))
  expect(payloads).toEqual([{ master_version_id: 'other', reference_asset_id: 'pasted', keep_master_outfit: true, confirmed: true }])
  expect(generate).toBeDisabled()
})
