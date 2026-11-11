import { CapacitorBarcodeScanner, CapacitorBarcodeScannerTypeHint } from '@capacitor/barcode-scanner'
import { normalizeBackend, saveBackend } from '@/lib/backend'

export async function checkBackend(origin: string) {
  const response = await fetch(`${origin}/health`, { signal: AbortSignal.timeout(8000) })
  const body = await response.json()
  if (!response.ok || body.status !== 'ok') throw new Error('The server did not return a healthy status.')
  const projects = await fetch(`${origin}/api/projects`, { signal: AbortSignal.timeout(8000) })
  if (!projects.ok || !Array.isArray(await projects.json())) throw new Error('The projects API is unavailable.')
}

export async function connectBackend(value: string) {
  const origin = normalizeBackend(value)
  await checkBackend(origin)
  saveBackend(origin)
  return origin
}

export async function scanAndConnectBackend() {
  const result = await CapacitorBarcodeScanner.scanBarcode({
    hint: CapacitorBarcodeScannerTypeHint.QR_CODE,
    scanInstructions: 'Scan the Character Studio backend QR code on your computer',
    scanButton: false,
    cancelButtonAccessibilityLabel: 'Cancel scan',
  })
  if (!result.ScanResult?.trim()) throw new Error('Scan cancelled. Your backend connection has not changed.')
  return connectBackend(result.ScanResult)
}
