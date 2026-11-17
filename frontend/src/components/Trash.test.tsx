import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import Trash from './Trash'

afterEach(() => vi.unstubAllGlobals())

it('restores an item and requires explicit confirmation before permanently deleting another', async () => {
  const calls: string[] = []
  let rows = ['job', 'asset'].map((kind, index) => ({ kind, id: String(index), title: `Item ${index}`, project_name: 'Alpha', asset_ids: [], error_message: null }))
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? 'GET'} ${url}`)
    if (url.endsWith('/restore') || init?.method === 'DELETE') {
      rows = rows.filter(item => !url.includes(`/${item.kind}/${item.id}`))
      return new Response('{}')
    }
    return new Response(JSON.stringify(rows))
  }))
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={qc}><Trash /></QueryClientProvider>)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Thùng rác' }))
  await screen.findByText('Item 0')
  await user.click(screen.getAllByRole('button', { name: 'Khôi phục' })[0])
  await waitFor(() => expect(screen.queryByText('Item 0')).not.toBeInTheDocument())
  expect(calls.some(call => call.includes('POST ') && call.endsWith('/trash/job/0/restore'))).toBe(true)
  await user.click(screen.getByRole('button', { name: 'Xoá vĩnh viễn' }))
  expect(calls.some(call => call.startsWith('DELETE'))).toBe(false)
  let confirmation = screen.getAllByRole('dialog').find(dialog => within(dialog).queryByRole('heading', { name: 'Xoá vĩnh viễn?' }))!
  await user.click(within(confirmation).getByRole('button', { name: 'Giữ lại' }))
  expect(calls.some(call => call.startsWith('DELETE'))).toBe(false)
  await user.click(screen.getByRole('button', { name: 'Xoá vĩnh viễn' }))
  confirmation = screen.getAllByRole('dialog').find(dialog => within(dialog).queryByRole('heading', { name: 'Xoá vĩnh viễn?' }))!
  await user.click(within(confirmation).getByRole('button', { name: 'Xoá vĩnh viễn' }))
  await screen.findByText('Thùng rác trống.')
  expect(calls.some(call => call.includes('DELETE ') && call.endsWith('/trash/asset/1'))).toBe(true)
  qc.clear()
})
