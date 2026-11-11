import { useEffect, useState } from 'react'
import { backendOrigin } from '@/lib/backend'
import { checkBackend, connectBackend, scanAndConnectBackend } from '@/lib/backendConnection'
import { Button } from '@/components/ui/button'

export default function BackendConnection() {
  const [open, setOpen] = useState(false)
  const [address, setAddress] = useState(backendOrigin)
  const [status, setStatus] = useState('Connecting…')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    checkBackend(backendOrigin()).then(() => { if (active) setStatus('Connected') }).catch(() => {
      if (active) { setStatus('Backend unavailable'); setOpen(true) }
    })
    return () => { active = false }
  }, [])

  async function connect(scan = false) {
    setBusy(true)
    setStatus(scan ? 'Scanning…' : 'Connecting…')
    try {
      const origin = await (scan ? scanAndConnectBackend() : connectBackend(address))
      setAddress(origin)
      // Reload drops cached projects and in-flight queries from the previous backend.
      window.location.reload()
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Connection failed')
    } finally { setBusy(false) }
  }

  return <section className="border-b bg-background px-4 py-3 text-sm">
    <div className="flex items-center justify-between gap-3">
      <span role="status">{status}</span>
      <div className="flex gap-2">
        <Button size="sm" disabled={busy} onClick={() => void connect(true)}>Scan QR</Button>
        <Button variant="outline" size="sm" onClick={() => setOpen(!open)}>Backend</Button>
      </div>
    </div>
    {open && <form className="mt-3 grid gap-3" onSubmit={event => { event.preventDefault(); void connect() }}>
      <label className="grid gap-1">Server address
        <input className="h-11 rounded-md border px-3" type="url" required value={address} onChange={event => setAddress(event.target.value)} autoCapitalize="none" autoCorrect="off" />
      </label>
      <p className="text-muted-foreground">Tailscale: connect your phone to the same tailnet, then scan the backend QR shown on your computer. You can also enter the server address here.</p>
      <Button type="submit" disabled={busy}>{busy ? 'Connecting…' : 'Test and connect'}</Button>
    </form>}
  </section>
}
