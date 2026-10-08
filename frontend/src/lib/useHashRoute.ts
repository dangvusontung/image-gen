import { useCallback, useSyncExternalStore } from 'react'

const subscribe = (cb: () => void) => {
  window.addEventListener('hashchange', cb)
  return () => window.removeEventListener('hashchange', cb)
}

export function parseProjectId(hash: string): string | null {
  const match = hash.match(/^#\/projects\/([\w-]+)/)
  return match ? match[1] : null
}

export function useHashRoute() {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash)
  const navigate = useCallback((to: string) => {
    window.location.hash = to
  }, [])
  return { projectId: parseProjectId(hash), navigate }
}
