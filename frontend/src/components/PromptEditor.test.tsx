import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { PromptEditor } from './GenerationUI'

afterEach(() => vi.unstubAllGlobals())

it.each(['master', 'concept', 'enhance', 'master_flux', 'turnaround_flux'])('copies only %s and updates the visible editor including an unsaved draft', async name => {
  let target = 'Original saved prompt'
  let payload: unknown
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.includes('/prompts/copy')) {
      payload = JSON.parse(init?.body as string)
      target = 'Copied source prompt'
      return new Response(JSON.stringify([{ name, body: target }]))
    }
    return new Response(JSON.stringify(url.includes('/prompts/') ? { name, body: target } : [{ id: 'source', name: 'Source project' }, { id: 'target', name: 'Target project' }]))
  }))
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={qc}><PromptEditor projectId="target" name={name} /></QueryClientProvider>)
  const user = userEvent.setup()
  await waitFor(() => expect(screen.getByLabelText(`Prompt ${name}`)).toHaveValue('Original saved prompt'))
  await user.clear(screen.getByLabelText(`Prompt ${name}`))
  await user.type(screen.getByLabelText(`Prompt ${name}`), 'Unsaved draft')
  await user.selectOptions(screen.getByLabelText(`Dự án nguồn cho prompt ${name}`), 'source')
  await user.click(screen.getByRole('button', { name: `Chép prompt ${name}`, exact: true }))
  await waitFor(() => expect(screen.getByLabelText(`Prompt ${name}`)).toHaveValue('Copied source prompt'))
  expect(payload).toEqual({ source_project_id: 'source', prompt_names: [name] })
  expect(screen.getByRole('status')).toHaveTextContent(`Đã chép và lưu prompt ${name}`)
  qc.clear()
})
