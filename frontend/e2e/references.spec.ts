import { expect, test } from '@playwright/test'

// 2×2 PNG
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGM8kWLEwMDAxMDAwMDAAAARKAFipiAqoAAAAABJRU5ErkJggg==',
  'base64',
)
const png = (name: string) => ({ name, mimeType: 'image/png', buffer: PNG })

test('create project, confirm rights, upload/reorder/remove photos, survive reload', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Tạo dự án mới' }).click()
  await page.getByLabel('Tên dự án').fill('Nhân vật E2E')
  await page.getByRole('button', { name: 'Tạo dự án', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Nhân vật E2E' })).toBeVisible()

  const refInput = page.locator('input[type=file]').first()
  await expect(refInput).toBeDisabled()
  await page.getByLabel(/Tôi xác nhận/).click()
  await expect(refInput).toBeEnabled()

  await refInput.setInputFiles([png('a.png'), png('b.png')])
  const tiles = page.locator('li img')
  await expect(tiles).toHaveCount(2)
  await expect(page.getByText('Ít ảnh tham chiếu')).toBeVisible()
  await expect(tiles.first()).toHaveAttribute('alt', 'a.png')
  // Thumbnail actually loads from the asset endpoint.
  await expect.poll(() => tiles.first().evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(2)

  await page.getByRole('button', { name: 'Chuyển ra sau' }).first().click()
  await expect(tiles.first()).toHaveAttribute('alt', 'b.png')

  await refInput.setInputFiles([{ name: 'fake.png', mimeType: 'image/png', buffer: Buffer.from('not an image') }])
  await expect(page.getByText(/fake\.png: File không phải ảnh hợp lệ/)).toBeVisible()

  await page.reload()
  await expect(page.getByRole('heading', { name: 'Nhân vật E2E' })).toBeVisible()
  await expect(page.getByLabel(/Tôi xác nhận/)).toBeChecked()
  await expect(tiles).toHaveCount(2)
  await expect(tiles.first()).toHaveAttribute('alt', 'b.png')

  await page.getByRole('button', { name: 'Xoá a.png' }).click()
  await expect(tiles).toHaveCount(1)

  await page.getByRole('button', { name: 'Tất cả dự án' }).click()
  const card = page.locator('[data-slot=card]').filter({ hasText: 'Nhân vật E2E' })
  await expect(card.getByText('1 ảnh')).toBeVisible()
  await expect.poll(() => card.locator('img').evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(2)
})

test('photos start selected and deselecting one keeps it out of generation', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Tạo dự án mới' }).click()
  await page.getByLabel('Tên dự án').fill('Chọn ảnh')
  await page.getByRole('button', { name: 'Tạo dự án', exact: true }).click()
  await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'PATCH' && r.url().includes('/api/projects/') && r.ok()),
    page.getByLabel(/Tôi xác nhận/).click(),
  ])
  await page
    .locator('input[type=file]')
    .first()
    .setInputFiles(['a', 'b', 'c'].map((n) => ({ name: `${n}.png`, mimeType: 'image/png', buffer: PNG })))
  await expect(page.locator('li img')).toHaveCount(3)

  // Everything is used by default.
  await expect(page.getByText('Dùng 3/3 ảnh để tạo nhân vật.')).toBeVisible()
  for (const name of ['a', 'b', 'c']) {
    await expect(page.getByLabel(`Dùng ${name}.png để tạo nhân vật`)).toBeChecked()
  }

  await page.getByLabel('Dùng b.png để tạo nhân vật').click()
  await expect(page.getByText('Dùng 2/3 ảnh để tạo nhân vật.')).toBeVisible()

  // Step 2 sends only what is still selected, and lists only those as its sources.
  await page.getByRole('tab', { name: '2. Nhân vật gốc' }).click()
  await expect(page.locator('img[data-source-image]')).toHaveCount(2)
  await page.getByRole('button', { name: 'Tạo nhân vật gốc', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Biến thể 1' })).toBeVisible()

  // Deselecting everything blocks generation instead of sending an empty request.
  await page.getByRole('tab', { name: '1. Ảnh tham chiếu' }).click()
  await page.getByRole('button', { name: 'Bỏ chọn tất cả' }).click()
  await expect(page.getByText('Chọn ít nhất một ảnh.')).toBeVisible()
  await page.getByRole('tab', { name: '2. Nhân vật gốc' }).click()
  await expect(page.getByRole('button', { name: 'Tạo nhân vật gốc', exact: true })).toBeDisabled()
  await expect(page.getByText('Chọn ít nhất một ảnh ở bước 1.')).toBeVisible()

  await page.getByRole('tab', { name: '1. Ảnh tham chiếu' }).click()
  await page.getByRole('button', { name: 'Chọn tất cả', exact: true }).click()
  await expect(page.getByText('Dùng 3/3 ảnh để tạo nhân vật.')).toBeVisible()
})
