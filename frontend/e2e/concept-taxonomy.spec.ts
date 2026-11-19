import { expect, test } from '@playwright/test'

test('labels and similar poses remain discoverable when grouping and numbering change', async ({ page, request }) => {
  const api = 'http://127.0.0.1:8100/api'
  const project = await (await request.post(`${api}/projects`, { data: { name: 'Catalog taxonomy' } })).json()
  const proposals = await (await request.get(`${api}/projects/${project.id}/concept-proposals`)).json()
  const flower = proposals.find((row: { slot: number }) => row.slot === 171)
  await page.goto(`/#/projects/${project.id}`)
  await page.getByRole('tab', { name: /Concept/ }).click()
  await page.getByText(/concept · Mở\/đóng danh sách/).click()
  await expect(page.getByLabel('Gom nhóm concept')).toHaveValue('family')
  const similar = page.getByRole('region', { name: 'Ôm gối & ôm chân', exact: true })
  await expect(similar.locator('[data-concept-progress="170"]')).toBeVisible()
  await expect(similar.locator('[data-concept-progress="183"]')).toBeVisible()
  const search = page.getByRole('searchbox', { name: 'Tìm concept' })
  await search.fill('C171 hoa su')
  await expect(page.locator('[data-concept-progress]')).toHaveCount(1)
  await expect(page.getByText(flower.label, { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: `Bookmark concept ${flower.display_number}`, exact: true })).toBeVisible()
  await page.getByLabel('Gom nhóm concept').selectOption('scene')
  await expect(page.getByRole('region', { name: flower.group, exact: true }).locator('[data-concept-progress="171"]')).toBeVisible()
  await expect(page.getByRole('button', { name: `Bookmark concept ${flower.display_number}`, exact: true })).toBeVisible()
  await search.fill('')
  await expect(page.locator('[data-concept-progress]')).toHaveCount(proposals.length)
})

test('renders a full-body catalog concept with the approved master outfit', async ({ page, request }) => {
  const api = 'http://127.0.0.1:8100/api'
  const project = await (await request.post(`${api}/projects`, { data: { name: 'Full-body catalog' } })).json()
  const base = `${api}/projects/${project.id}`
  await request.patch(base, { data: { rights_confirmed: true } })
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGM8kWLEwMDAxMDAwMDAAAARKAFipiAqoAAAAABJRU5ErkJggg==', 'base64')
  expect((await request.post(`${base}/assets`, {
    multipart: { files: { name: 'face.png', mimeType: 'image/png', buffer: png }, kind: 'reference' },
  })).ok()).toBeTruthy()
  expect((await request.post(`${base}/master/generate`, { data: {} })).ok()).toBeTruthy()
  await expect.poll(async () => (await (await request.get(`${base}/workflow`)).json()).masters[0]?.job.status).toBe('succeeded')
  const master = (await (await request.get(`${base}/workflow`)).json()).masters[0]
  expect((await request.post(`${base}/master/${master.id}/approve`)).ok()).toBeTruthy()

  await page.goto(`/#/projects/${project.id}`)
  await page.getByRole('tab', { name: /Concept/ }).click()
  await page.getByLabel('Đổi trang phục concept').selectOption('master')
  await page.getByText(/concept · Mở\/đóng danh sách/).click()
  await page.getByRole('searchbox', { name: 'Tìm concept' }).fill('C191')
  await expect(page.locator('[data-concept-progress]')).toHaveCount(1)
  await expect(page.getByText('Khung toàn thân', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Chỉ chọn các concept đang hiện' }).click()
  const response = page.waitForResponse(res => res.url().endsWith('/concepts/generate') && res.request().method() === 'POST')
  await page.getByRole('button', { name: 'Tạo ảnh cho 1 concept' }).click()
  const generated = await response
  expect(generated.status()).toBe(201)
  const [jobId] = (await generated.json()).job_ids
  await expect.poll(async () => (await (await request.get(`${api}/jobs/${jobId}`)).json()).status).toBe('succeeded')
  const job = await (await request.get(`${api}/jobs/${jobId}`)).json()
  expect(job.meta).toMatchObject({ full_body: true, master_outfit: true })
  expect(job.prompt).toContain('clear space above the head and below the soles')
})
