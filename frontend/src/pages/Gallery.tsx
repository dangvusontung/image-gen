import ImageGallery from '@/components/ImageGallery'
import { Button } from '@/components/ui/button'

export default function Gallery({ onBack }: { onBack: () => void }) {
  return <main className="mx-auto max-w-7xl px-6 py-8 pb-28">
    <Button variant="ghost" onClick={onBack}>← Tất cả dự án</Button>
    <h1 className="my-6 text-2xl font-semibold">Gallery tổng</h1>
    <ImageGallery />
  </main>
}
