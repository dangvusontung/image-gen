import { useCallback, useEffect, useState } from 'react'

const KEY = 'favourite-models'

/** A favourite is identified across providers, since model ids are only unique per provider. */
export const favouriteId = (provider: string, modelId: string) => `${provider}/${modelId}`

function read(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || '[]')
    return Array.isArray(raw) ? raw.filter((v): v is string => typeof v === 'string') : []
  } catch {
    return []
  }
}

/** Starred models, shared across every project and remembered in this browser. */
export function useFavouriteModels() {
  const [favourites, setFavourites] = useState<string[]>(read)

  useEffect(() => {
    // Keep other tabs and the other pickers in step.
    const sync = (e: StorageEvent) => { if (e.key === KEY) setFavourites(read()) }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [])

  const toggle = useCallback((provider: string, modelId: string) => {
    const id = favouriteId(provider, modelId)
    setFavourites((prev) => {
      const next = prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id]
      try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* storage may be unavailable */ }
      return next
    })
  }, [])

  const isFavourite = useCallback(
    (provider: string, modelId: string) => favourites.includes(favouriteId(provider, modelId)),
    [favourites],
  )

  return { favourites, toggle, isFavourite }
}
