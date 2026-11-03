import { expect, test } from '@playwright/test'

test('custom hairstyle persists per project and reaches the generation prompt', async ({ page, request }) => {
  const project = await (await request.post('http://127.0.0.1:8100/api/projects', { data: { name: 'Hair design E2E' } })).json()
  const base = `http://127.0.0.1:8100/api/projects/${project.id}`
  await request.patch(base, { data: { rights_confirmed: true } })
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGM8kWLEwMDAxMDAwMDAAAARKAFipiAqoAAAAABJRU5ErkJggg==', 'base64')
  await request.post(`${base}/assets`, { multipart: { files: { name: 'face.png', mimeType: 'image/png', buffer: png }, kind: 'reference' } })
  await page.goto('/')
  await page.getByText('Hair design E2E', { exact: true }).click()
  await page.getByRole('tab', { name: '2. Nhân vật gốc' }).click()
  await expect(page.getByLabel('Kiểu tóc', { exact: true })).toHaveValue('reference')
  await page.getByLabel('Kiểu tóc', { exact: true }).selectOption('custom')
  const generate = page.getByRole('button', { name: 'Tạo nhân vật gốc', exact: true })
  await expect(generate).toBeDisabled()
  await page.getByLabel('Mô tả kiểu tóc', { exact: true }).fill('Auburn shoulder-length curls with curtain bangs')
  await page.reload()
  await page.getByRole('tab', { name: '2. Nhân vật gốc' }).click()
  await expect(page.getByLabel('Kiểu tóc', { exact: true })).toHaveValue('custom')
  await expect(page.getByLabel('Mô tả kiểu tóc', { exact: true })).toHaveValue('Auburn shoulder-length curls with curtain bangs')
  await generate.click()
  await expect.poll(async () => {
    const workflow = await (await request.get(`${base}/workflow`)).json()
    return workflow.masters[0]?.job.prompt ?? ''
  }).toContain('Auburn shoulder-length curls with curtain bangs')
})
