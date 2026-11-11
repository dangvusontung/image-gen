import { Capacitor } from '@capacitor/core'

const KEY = 'character-studio.backend'
export const isAndroid = () => Capacitor.getPlatform() === 'android'

export function normalizeBackend(value: string): string {
  const url = new URL(value.trim())
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('Enter a server address such as http://127.0.0.1:8000 (without a path).')
  }
  return url.origin
}

export function backendOrigin(): string {
  if (!isAndroid()) return ''
  return localStorage.getItem(KEY) ?? 'http://127.0.0.1:8000'
}

export const apiUrl = (path: string) => `${backendOrigin()}/api${path}`

export function saveBackend(value: string) {
  localStorage.setItem(KEY, normalizeBackend(value))
}
