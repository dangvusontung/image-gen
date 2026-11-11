import { App } from '@capacitor/app'
import { registerPlugin } from '@capacitor/core'
import { backendOrigin, isAndroid } from '@/lib/backend'

const Downloads = registerPlugin<{ download(options: { url: string }): Promise<void> }>('StudioDownloads')

export function initializeAndroid() {
  if (!isAndroid()) return
  document.documentElement.classList.add('android-app')
  void App.addListener('backButton', () => {
    const closeDialog = document.querySelector<HTMLElement>('[data-slot="dialog-content"] [data-slot="dialog-close"]')
    if (closeDialog) { closeDialog.click(); return }
    if (window.location.hash && window.location.hash !== '#/') window.location.hash = '/'
    else void App.minimizeApp()
  })
  document.addEventListener('click', event => {
    const anchor = (event.target as Element).closest<HTMLAnchorElement>('a[href]')
    if (!anchor) return
    const url = new URL(anchor.href)
    if (url.origin !== backendOrigin() || !/^\/api\/(assets\/[^/]+\/download|projects\/[^/]+\/(export|contact-sheet))$/.test(url.pathname)) return
    event.preventDefault()
    void Downloads.download({ url: url.href }).catch(() => {
      window.alert('Download failed. Check your backend connection and try again.')
    })
  })
}
