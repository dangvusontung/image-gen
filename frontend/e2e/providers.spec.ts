import { expect, test } from '@playwright/test'

const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGM8kWLEwMDAxMDAwMDAAAARKAFipiAqoAAAAABJRU5ErkJggg==',
  'base64',
)

test('provider settings show key status, capabilities and connection test', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Nhà cung cấp & model' }).click()
  await expect(page.getByRole('heading', { name: 'Nhà cung cấp & model' })).toBeVisible()

  const card = (name: string) => page.locator('[data-slot=card]').filter({ hasText: name })
  await expect(card('Google Gemini')).toContainText('Chưa có API key')
  await expect(card('Google Gemini')).toContainText('gemini-nano-banana-2.1')
  await expect(card('Google Gemini')).toContainText('GEMINI_API_KEY=')
  await expect(card('Black Forest Labs')).toContainText('flux-2-pro')
  await expect(card('Midjourney')).toContainText('Không hỗ trợ')
  await expect(card('Midjourney').getByRole('button', { name: 'Kiểm tra kết nối' })).toHaveCount(0)
  await expect(page.getByText(/Chi phí job 24h/)).toContainText('$0.00')
  await expect(page.getByText(/Giới hạn ứng dụng/)).toContainText('Không giới hạn')

  await card('Mock').getByRole('button', { name: 'Kiểm tra kết nối' }).click()
  await expect(card('Mock').getByRole('status')).toHaveText('Mock provider luôn sẵn sàng')
  await card('Google Gemini').getByRole('button', { name: 'Kiểm tra kết nối' }).click()
  await expect(card('Google Gemini').getByRole('status')).toHaveText('Chưa cấu hình GEMINI_API_KEY')

  // Keys must never reach the browser.
  const providersJson = await page.evaluate(() => fetch('/api/providers').then((r) => r.text()))
  expect(providersJson).not.toMatch(/AIza|x-key|api_key/i)
})

test('project model picker persists and warns when references exceed the model limit', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Tạo dự án mới' }).click()
  await page.getByLabel('Tên dự án').fill('Chọn model')
  await page.getByRole('button', { name: 'Tạo dự án', exact: true }).click()
  await page.getByRole('checkbox').click()
  await page
    .locator('input[type=file]')
    .first()
    .setInputFiles(['a', 'b', 'c'].map((n) => ({ name: `${n}.png`, mimeType: 'image/png', buffer: PNG })))
  await expect(page.locator('li img')).toHaveCount(3)

  await page.getByLabel('Nhà cung cấp').click()
  await expect(page.getByRole('option', { name: /Google Gemini/ })).toHaveAttribute('data-disabled', '')
  await page.keyboard.press('Escape')

  await page.getByLabel('Model').click()
  await page.getByRole('option', { name: 'Mock (tối đa 2 ảnh tham chiếu)' }).click()
  await expect(page.getByText(/nhận tối đa 2 ảnh tham chiếu, dự án đang có 3/)).toBeVisible()

  await page.reload()
  await expect(page.getByLabel('Model')).toContainText('Mock (tối đa 2 ảnh tham chiếu)')
  await page.getByRole('button', { name: 'Xoá a.png' }).click()
  await expect(page.getByText(/nhận tối đa 2 ảnh tham chiếu/)).toHaveCount(0)
})
