import { useCallback, useSyncExternalStore } from 'react'

export type Route = { page: 'dashboard' } | { page: 'settings' } | { page: 'project'; projectId: string }

const subscribe = (cb: () => void) => {
  window.addEventListener('hashchange', cb)
  return () => window.removeEventListener('hashchange', cb)
}

export function parseRoute(hash: string): Route {
  const project = hash.match(/^#\/projects\/([\w-]+)/)
  if (project) return { page: 'project', projectId: project[1] }
  if (hash.startsWith('#/settings')) return { page: 'settings' }
  return { page: 'dashboard' }
}

export function useHashRoute() {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash)
  const navigate = useCallback((to: string) => {
    window.location.hash = to
  }, [])
  return { route: parseRoute(hash), navigate }
}
