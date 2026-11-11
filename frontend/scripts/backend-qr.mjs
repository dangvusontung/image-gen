import { execFileSync } from 'node:child_process'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import QRCode from 'qrcode'

let address = process.argv[2]
if (!address) {
  const status = JSON.parse(execFileSync('tailscale', ['status', '--json'], { encoding: 'utf8' }))
  const ip = status.Self?.TailscaleIPs?.find(ip => !ip.includes(':'))
  if (status.BackendState !== 'Running' || !ip) throw new Error('Connect Tailscale, or pass your backend URL as an argument.')
  address = `http://${ip}:8000`
}
const url = new URL(address)
if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
  throw new Error('Pass a backend origin without credentials or a path.')
}
const health = await fetch(`${url.origin}/health`, { signal: AbortSignal.timeout(8000) })
if (!health.ok || (await health.json()).status !== 'ok') throw new Error('The backend is not healthy at this address.')
const output = new URL('../../data/android-backend-qr.png', import.meta.url)
await mkdir(new URL('.', output), { recursive: true })
await QRCode.toFile(fileURLToPath(output), url.origin, { width: 720, margin: 4, errorCorrectionLevel: 'M' })
console.log(`Backend: ${url.origin}\nQR code: ${fileURLToPath(output)}`)
