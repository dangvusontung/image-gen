import { useState } from 'react'
import { Button } from '@/components/ui/button'

export default function CopyPromptButton({ text }: { text: string }) {
  const [status, setStatus] = useState('')
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setStatus('Đã copy prompt.')
    } catch {
      setStatus('Không copy được. Hãy chọn nội dung trong ô và sao chép thủ công.')
    }
  }
  return <>
    <Button type="button" variant="outline" disabled={!text} onClick={() => void copy()}>Copy prompt</Button>
    {status && <span role="status" className="self-center text-xs">{status}</span>}
  </>
}
