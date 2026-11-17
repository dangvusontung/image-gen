import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import QRCode from 'qrcode'
import { QrCodeIcon } from 'lucide-react'
import { request } from '@/api/client'
import { normalizeBackend } from '@/lib/backend'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from '@/components/ui/dialog'

export default function PhoneConnectionQR() {
  const [open, setOpen] = useState(false)
  const [address, setAddress] = useState('')
  const [qr, setQr] = useState('')
  const [error, setError] = useState('')
  const connection = useQuery({ queryKey: ['connection-info'], enabled: open,
    queryFn: () => request<{ origin: string | null; transport: string | null }>('/connection-info'), staleTime: 30_000 })
  useEffect(() => { if (connection.data?.origin) setAddress(connection.data.origin) }, [connection.data])
  useEffect(() => {
    let active = true
    setQr(''); setError('')
    if (address.trim()) {
      try {
        const origin = normalizeBackend(address)
        const host = new URL(origin).hostname
        if (host === 'localhost' || host === '127.0.0.1' || host === '[::1]') throw new Error('Use a network address reachable from your phone, not localhost.')
        void QRCode.toDataURL(origin, { width: 320, margin: 3, errorCorrectionLevel: 'M' })
          .then(value => { if (active) setQr(value) }).catch(() => { if (active) setError('Could not create QR code.') })
      } catch (e) { setError(e instanceof Error ? e.message : 'Invalid backend address.') }
    }
    return () => { active = false }
  }, [address])
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button variant="outline" size="lg"><QrCodeIcon /> Connect phone</Button></DialogTrigger>
    <DialogContent className="max-h-[90vh] overflow-auto sm:max-w-md">
      <DialogTitle>Connect your phone</DialogTitle>
      <DialogDescription>Enable Tailscale on your phone on the same tailnet. In the native app, open the connection screen and tap Scan QR, then Test and connect.</DialogDescription>
      {connection.isPending && <p className="text-sm">Finding the backend address…</p>}
      {qr && <img className="mx-auto w-full max-w-80 rounded-lg" src={qr} alt="Backend connection QR code" />}
      <label className="grid gap-2 text-sm">Backend address
        <Input aria-label="Phone backend address" value={address} onChange={event => setAddress(event.target.value)} placeholder="http://100.x.x.x:8000" />
      </label>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {connection.error && <p role="alert" className="text-sm text-destructive">Could not detect an address. Enter your phone-reachable backend address.</p>}
      {!connection.isPending && !address && <p className="text-sm text-muted-foreground">No shared address detected. Enter an existing backend address reachable from your phone.</p>}
      <p className="text-xs text-muted-foreground">This QR contains only the backend address. It does not contain provider API keys.</p>
    </DialogContent>
  </Dialog>
}
