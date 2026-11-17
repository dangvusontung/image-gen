import { expect, test } from '@playwright/test'

test('concept creation history and filters belong to the current project', async ({ page, request }) => {
  const api = 'http://127.0.0.1:8100/api'
  const create = async (name: string) => (await (await request.post(`${api}/projects`, { data: { name } })).json()).id as string
  const first = await create('Concept history first')
  const second = await create('Concept history second')
  await page.route(`**/api/projects/${first}/concepts`, route => route.fulfill({ json: [{
    id: 'history-row', slot: 1, run: 2, revision: 1, bookmark_key: 'default:1',
    mood: 'Existing result', camera: '', brief: {}, stale: false, master_version_id: 'master', turnaround_version_id: null,
    job: { id: 'history-job', provider: 'mock', model: 'mock', settings: {}, status: 'succeeded', output_asset_ids: ['existing-image'], error_message: null },
  }] }))
  const open = async (id: string) => {
    await page.goto(`/#/projects/${id}`)
    await page.getByRole('tab', { name: /Concept/ }).click()
    await page.getByText(/concept · Mở\/đóng danh sách/).click()
  }
  await open(first)
  const search = page.getByRole('searchbox', { name: 'Tìm concept' })
  await search.fill('id:80')
  await expect(page.locator('[data-concept-progress="80"]')).toBeVisible()
  await expect(page.locator('[data-concept-progress]')).toHaveCount(1)
  await search.fill('khong-co-concept-nay')
  await expect(page.getByText('Không có concept khớp bộ lọc.')).toBeVisible()
  await page.getByRole('button', { name: 'Xóa tìm kiếm' }).click()
  const state = page.locator('[data-concept-progress="1"]')
  await expect(state).toContainText('Đã tạo · 1 ảnh')
  await expect(page.getByRole('img', { name: 'Ảnh đã tạo ·' })).toHaveCount(1)
  await page.getByRole('button', { name: /Mở kết quả concept .* ảnh 1/ }).click()
  await expect(page.getByRole('dialog')).toContainText('Đợt 2 · v1')
  await page.keyboard.press('Escape')
  await state.getByRole('button', { name: 'Xem kết quả' }).click()
  await expect(page.getByRole('dialog')).toContainText('Đợt 2 · v1')
  await page.keyboard.press('Escape')
  await page.getByLabel('Lọc trạng thái tạo concept').selectOption('created')
  await expect(page.locator('[data-concept-progress]')).toHaveCount(1)
  await open(second)
  await page.getByLabel('Lọc trạng thái tạo concept').selectOption('all')
  await expect(page.locator('[data-concept-progress="1"]')).toContainText('Chưa tạo')
  await expect(page.locator('[data-concept-progress="1"] button')).toHaveCount(0)
})
