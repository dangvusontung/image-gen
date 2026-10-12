import { expect, test } from '@playwright/test'

const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGM8kWLEwMDAxMDAwMDAAAARKAFipiAqoAAAAABJRU5ErkJggg==',
  'base64',
)

test('the generation popup announces each finish and can be dismissed', async ({ page, request }) => {
  const created = await request.post('http://127.0.0.1:8100/api/projects', { data: { name: 'Theo dõi job' } })
  const project = await created.json()
  const base = `http://127.0.0.1:8100/api/projects/${project.id}`
  await request.patch(base, { data: { rights_confirmed: true } })
  await request.post(`${base}/assets`, {
    multipart: { files: { name: 'face.png', mimeType: 'image/png', buffer: PNG }, kind: 'reference' },
  })

  await page.goto('/')
  await page.getByText('Theo dõi job', { exact: true }).click()
  const popup = page.getByRole('region', { name: 'Tiến trình tạo ảnh' })
  // Nothing is running, so the popup stays out of the way.
  await expect(popup).toHaveCount(0)

  await page.getByRole('tab', { name: '2. Nhân vật gốc' }).click()
  await page.getByLabel('Số biến thể').selectOption('2')
  await page.getByRole('button', { name: 'Tạo nhân vật gốc', exact: true }).click()

  // Mock jobs finish in well under one poll interval, so the running list is covered by the
  // component test; what must hold end to end is that both finishes are still announced.
  await expect(popup.getByRole('listitem').filter({ hasText: 'Nhân vật gốc · Hoàn tất' })).toHaveCount(2)

  // The note can be dismissed by hand, and the popup disappears once empty.
  const notes = popup.getByRole('button', { name: /^Ẩn thông báo/ })
  await notes.first().click()
  await notes.first().click()
  await expect(popup).toHaveCount(0)
})
