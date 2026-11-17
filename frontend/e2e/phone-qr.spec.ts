import { expect, test } from '@playwright/test'

test('phone QR uses the advertised backend address and rejects localhost', async ({ page }) => {
  await page.route('**/api/connection-info', route => route.fulfill({ json: { origin: 'http://100.72.216.79:8000', transport: 'tailscale' } }))
  await page.goto('/')
  await page.getByRole('button', { name: 'Connect phone' }).click()
  const address = page.getByLabel('Phone backend address')
  const qr = page.getByAltText('Backend connection QR code')
  await expect(address).toHaveValue('http://100.72.216.79:8000')
  await expect(qr).toHaveAttribute('src', /^data:image\/png;base64,/)
  await address.fill('http://localhost:8000')
  await expect(page.getByRole('alert')).toContainText('not localhost')
  await expect(qr).toHaveCount(0)
  await address.fill('http://100.72.216.79:8000')
  await expect(qr).toBeVisible()
  await page.screenshot({ path: '/tmp/character-studio-phone-qr.png' })
})
