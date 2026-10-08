import { UploadIcon } from 'lucide-react'
import { useId, useState } from 'react'
import { cn } from '@/lib/utils'
import { ACCEPTED_TYPES, MAX_FILE_BYTES } from '@/lib/upload'

export function UploadDropzone({
  onFiles,
  disabled,
  label,
  hint,
}: {
  onFiles: (files: File[]) => void
  disabled?: boolean
  label: string
  hint?: string
}) {
  const inputId = useId()
  const [dragging, setDragging] = useState(false)

  return (
    <label
      htmlFor={inputId}
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        if (!disabled) onFiles(Array.from(e.dataTransfer.files))
      }}
      aria-disabled={disabled}
      className={cn(
        'flex cursor-pointer flex-col items-center gap-1 rounded-xl border-2 border-dashed p-6 text-center transition-colors',
        dragging ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50',
        disabled && 'cursor-not-allowed opacity-50 hover:border-border',
      )}
    >
      <UploadIcon className="mb-1 size-6 text-muted-foreground" />
      <span className="font-medium">{label}</span>
      <span className="text-sm text-muted-foreground">
        Kéo thả hoặc bấm để chọn · JPEG/PNG/WEBP · tối đa {MAX_FILE_BYTES / 1024 / 1024}MB/ảnh
      </span>
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
      <input
        id={inputId}
        type="file"
        multiple
        accept={ACCEPTED_TYPES.join(',')}
        disabled={disabled}
        className="sr-only"
        onChange={(e) => {
          onFiles(Array.from(e.target.files ?? []))
          e.target.value = ''
        }}
      />
    </label>
  )
}
