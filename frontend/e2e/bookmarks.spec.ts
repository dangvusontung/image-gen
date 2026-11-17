import { expect, test } from '@playwright/test'

test('concept bookmarks persist on backend and share across characters without local storage', async ({ page, request }) => {
  const api = 'http://127.0.0.1:8100/api'
  const create = async (name: string) => (await (await request.post(`${api}/projects`, { data: { name } })).json()).id as string
  const first = await create('Shared bookmark first')
  const second = await create('Shared bookmark second')
  const open = async (id: string) => {
    await page.goto(`/#/projects/${id}`)
    await page.getByRole('tab', { name: /Concept/ }).click()
    await page.getByText(/concept · Mở\/đóng danh sách/, { exact: false }).click()
  }
  await open(first)
  const star = page.getByRole('button', { name: /^Bookmark concept/ }).first()
  await expect(star).toBeEnabled()
  const label = (await star.getAttribute('aria-label'))!
  await star.click()
  await expect(star).toHaveAttribute('aria-pressed', 'true')
  await expect.poll(async () => (await (await request.get(`${api}/concept-bookmarks`)).json()).keys.length).toBe(1)
  await page.evaluate(() => localStorage.clear())
  await open(second)
  const shared = page.getByRole('button', { name: label, exact: true })
  await expect(shared).toHaveAttribute('aria-pressed', 'true')
  await shared.click()
  await expect(shared).toHaveAttribute('aria-pressed', 'false')
  await open(first)
  await expect(page.getByRole('button', { name: label, exact: true })).toHaveAttribute('aria-pressed', 'false')
})
