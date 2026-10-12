import { useCallback, useEffect, useState } from 'react'

const key = (projectId: string) => `image-size:${projectId}`

/** Output size, chosen once per project in the pinned switcher and used by every step. */
export function useImageSize(projectId: string) {
  const [size, setSizeState] = useState(() => {
    try { return localStorage.getItem(key(projectId)) ?? '' } catch { return '' }
  })

  useEffect(() => {
    const sync = (e: StorageEvent) => { if (e.key === key(projectId)) setSizeState(e.newValue ?? '') }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [projectId])

  const setSize = useCallback((value: string) => {
    setSizeState(value)
    try {
      if (value) localStorage.setItem(key(projectId), value)
      else localStorage.removeItem(key(projectId))
    } catch { /* storage may be unavailable */ }
    // Other components on the page hold their own copy, so tell them directly.
    window.dispatchEvent(new StorageEvent('storage', { key: key(projectId), newValue: value }))
  }, [projectId])

  return [size, setSize] as const
}
