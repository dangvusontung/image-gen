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
  await page.getByRole('checkbox').click()
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
  await expect(page.getByRole('checkbox')).toBeChecked()
  await expect(tiles).toHaveCount(2)
  await expect(tiles.first()).toHaveAttribute('alt', 'b.png')

  await page.getByRole('button', { name: 'Xoá a.png' }).click()
  await expect(tiles).toHaveCount(1)

  await page.getByRole('button', { name: 'Tất cả dự án' }).click()
  const card = page.locator('[data-slot=card]').filter({ hasText: 'Nhân vật E2E' })
  await expect(card.getByText('1 ảnh')).toBeVisible()
  await expect.poll(() => card.locator('img').evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(2)
})
