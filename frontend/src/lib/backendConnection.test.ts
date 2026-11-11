import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { backendOrigin } from './backend'
import { connectBackend, scanAndConnectBackend } from './backendConnection'

const scanner = vi.hoisted(() => vi.fn())
vi.mock('@capacitor/core', () => ({ Capacitor: { getPlatform: () => 'android' } }))
vi.mock('@capacitor/barcode-scanner', () => ({
  CapacitorBarcodeScanner: { scanBarcode: scanner }, CapacitorBarcodeScannerTypeHint: { QR_CODE: 0 },
}))
let fetchMock: ReturnType<typeof vi.fn>
beforeEach(() => {
  localStorage.clear()
  scanner.mockReset()
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => vi.unstubAllGlobals())

it('scans a URL, checks both APIs, then saves the backend', async () => {
  scanner.mockResolvedValue({ ScanResult: 'http://100.72.216.79:8000/' })
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ status: 'ok' })))
    .mockResolvedValueOnce(new Response('[]'))
  expect(await scanAndConnectBackend()).toBe('http://100.72.216.79:8000')
  expect(scanner).toHaveBeenCalledWith(expect.objectContaining({ hint: 0 }))
  expect(fetchMock.mock.calls.map(call => call[0])).toEqual([
    'http://100.72.216.79:8000/health', 'http://100.72.216.79:8000/api/projects',
  ])
  expect(backendOrigin()).toBe('http://100.72.216.79:8000')
})

it('does not change the backend after cancellation or an unrelated QR code', async () => {
  for (const ScanResult of ['', 'WIFI:T:WPA;S:network;', 'https://host/path']) {
    scanner.mockResolvedValue({ ScanResult })
    await expect(scanAndConnectBackend()).rejects.toThrow()
  }
  expect(fetchMock).not.toHaveBeenCalled()
  expect(backendOrigin()).toBe('http://127.0.0.1:8000')
})

it('does not save an unreachable server or a healthy server missing the workflow API', async () => {
  fetchMock.mockRejectedValueOnce(new Error('Network unavailable'))
  await expect(connectBackend('http://100.72.216.79:8000')).rejects.toThrow('Network unavailable')
  fetchMock.mockResolvedValueOnce(new Response('{"status":"ok"}'))
    .mockResolvedValueOnce(new Response('{"detail":"Not found"}', { status: 404 }))
  await expect(connectBackend('http://100.72.216.79:8000')).rejects.toThrow('projects API')
  expect(backendOrigin()).toBe('http://127.0.0.1:8000')
})
