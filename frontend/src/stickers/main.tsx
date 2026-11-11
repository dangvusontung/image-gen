import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/api/client'
import StickerStudio from './StickerStudio'
import '@fontsource-variable/geist'
import './stickers.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode><QueryClientProvider client={queryClient}><StickerStudio /></QueryClientProvider></StrictMode>,
)
