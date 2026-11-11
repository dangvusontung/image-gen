import { beforeEach, expect, it, vi } from 'vitest'
import { apiUrl, backendOrigin, normalizeBackend, saveBackend } from './backend'

const platform = vi.hoisted(() => ({ value: 'web' }))
vi.mock('@capacitor/core', () => ({ Capacitor: { getPlatform: () => platform.value } }))

beforeEach(() => { localStorage.clear(); platform.value = 'web' })

it('keeps browser API and media requests on the existing proxy', () => {
  expect(apiUrl('/projects')).toBe('/api/projects')
})

it('uses the USB backend on Android and persists an explicit server', () => {
  platform.value = 'android'
  expect(backendOrigin()).toBe('http://127.0.0.1:8000')
  saveBackend(' http://10.0.2.2:8000/ ')
  expect(apiUrl('/assets/image/content')).toBe('http://10.0.2.2:8000/api/assets/image/content')
})

it('rejects credentials, paths and non-HTTP addresses', () => {
  for (const value of ['file:///tmp', 'http://user:secret@host', 'http://host/api', 'http://host/?key=secret', 'http://host/#fragment']) {
    expect(() => normalizeBackend(value)).toThrow()
  }
})
