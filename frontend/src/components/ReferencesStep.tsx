import { ArrowLeftIcon, ArrowRightIcon, RepeatIcon, ShieldCheckIcon, Trash2Icon, TriangleAlertIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  assetUrl,
  useDeleteAsset,
  useReorderAssets,
  useSelectAsset,
  useUpdateAssetKind,
  useUpdateProject,
  useUploadAssets,
  type Asset,
  type AssetKind,
  type ProjectDetail,
} from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { UploadDropzone } from '@/components/UploadDropzone'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { formatBytes, LIMITS, moveItem, prevalidateFiles, referenceCountWarning } from '@/lib/upload'

const KIND_LABEL: Record<AssetKind, string> = { reference: 'Ảnh tham chiếu', side_profile: 'Ảnh nghiêng', template: 'Ảnh mẫu' }

export default function ReferencesStep({ project }: { project: ProjectDetail }) {
  const updateProject = useUpdateProject(project.id)
  const upload = useUploadAssets(project.id)
  const reorder = useReorderAssets(project.id)
  const [clientErrors, setClientErrors] = useState<string[]>([])
  const [pasteKind, setPasteKind] = useState<AssetKind>('reference')

  const byKind = (kind: AssetKind) => project.assets.filter((a) => a.kind === kind)
  const references = byKind('reference')
  const sideProfiles = byKind('side_profile')
  const templates = byKind('template')
  const warning = referenceCountWarning(references.length)

  const handleFiles = (kind: AssetKind) => (files: File[]) => {
    if (!project.rights_confirmed || upload.isPending) return
    const { accepted, errors } = prevalidateFiles(files, kind, byKind(kind).length)
    setClientErrors(errors)
    if (accepted.length) upload.mutate({ files: accepted, kind })
  }

  useEffect(() => {
    const paste = (event: ClipboardEvent) => {
      const target = event.target
      if (target instanceof HTMLElement && target.closest('input, textarea, [contenteditable="true"], [role="textbox"]')) return
      if (!project.rights_confirmed || upload.isPending || !event.clipboardData) return
      const files = Array.from(event.clipboardData.files).filter(file => file.type.startsWith('image/'))
      if (!files.length) return
      event.preventDefault()
      handleFiles(pasteKind)(files)
    }
    document.addEventListener('paste', paste)
    return () => document.removeEventListener('paste', paste)
  })

  const move = (kind: AssetKind, from: number, to: number) => {
    const moved = moveItem(byKind(kind), from, to)
    const other = project.assets.filter((a) => a.kind !== kind)
    const ordered = kind === 'reference' ? [...moved, ...other] : [...other, ...moved]
    reorder.mutate(ordered.map((a) => a.id))
  }

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheckIcon className="size-5" /> Quyền sử dụng ảnh & quyền riêng tư
          </CardTitle>
          <CardDescription>
            Khi tạo nhân vật (bước sau), ảnh tham chiếu sẽ được gửi tới nhà cung cấp AI bạn chọn (Google Gemini hoặc
            Black Forest Labs). Ảnh lưu cục bộ trên máy này; xoá ảnh ở đây không xoá được bản đã gửi cho nhà cung cấp — xem
            chính sách lưu trữ của họ.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-start gap-3">
            <Checkbox
              id="rights"
              checked={project.rights_confirmed}
              disabled={updateProject.isPending}
              onCheckedChange={(checked) => updateProject.mutate({ rights_confirmed: checked === true })}
            />
            <Label htmlFor="rights" className="leading-snug font-normal">
              Tôi xác nhận đây là ảnh của tôi, hoặc tôi đã được người trong ảnh cho phép sử dụng để tạo nhân vật.
            </Label>
          </div>
          {updateProject.error && <div className="mt-3"><ErrorAlert error={updateProject.error} /></div>}
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center gap-3 rounded-lg border p-4 text-sm">
        <label>Dán ảnh vào <select aria-label="Dán ảnh vào" className="ml-2 rounded border p-2" value={pasteKind}
          disabled={!project.rights_confirmed || upload.isPending} onChange={event => setPasteKind(event.target.value as AssetKind)}>
          <option value="reference">Ảnh tham chiếu</option>
          <option value="side_profile">Ảnh nghiêng</option>
        </select></label>
        <p>Sao chép ảnh, rồi nhấn Ctrl+V (Mac: ⌘V) tại bước này để tải lên.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <UploadDropzone
          label={`Ảnh tham chiếu (${references.length}/${LIMITS.reference})`}
          hint="Nên dùng 3–8 ảnh rõ mặt, nhiều góc, cùng một người"
          disabled={!project.rights_confirmed || upload.isPending || references.length >= LIMITS.reference}
          onFiles={handleFiles('reference')}
        />
        <UploadDropzone
          label={`Ảnh nghiêng — tùy chọn (${sideProfiles.length}/${LIMITS.side_profile})`}
          hint="Giúp turnaround góc 90° chính xác hơn"
          disabled={!project.rights_confirmed || upload.isPending || sideProfiles.length >= LIMITS.side_profile}
          onFiles={handleFiles('side_profile')}
        />
        <UploadDropzone
          label={`Ảnh mẫu — tùy chọn (${templates.length}/${LIMITS.template})`}
          hint="Ảnh định hướng phong cách: chất liệu, bố cục, ánh sáng. Không lấy khuôn mặt từ ảnh này."
          disabled={!project.rights_confirmed || upload.isPending || templates.length >= LIMITS.template}
          onFiles={handleFiles('template')}
        />
      </div>

      {!project.rights_confirmed && (
        <p className="text-sm text-muted-foreground">Hãy xác nhận quyền sử dụng ảnh ở trên để bật tải ảnh.</p>
      )}
      {upload.isPending && <p className="text-sm text-muted-foreground">Đang tải ảnh lên…</p>}
      {clientErrors.length > 0 && <ErrorAlert title="Một số ảnh bị bỏ qua" error={clientErrors.join('\n')} />}
      {upload.error && <ErrorAlert title="Tải ảnh thất bại" error={upload.error} />}
      {reorder.error && <ErrorAlert title="Không đổi được thứ tự" error={reorder.error} />}
      {warning && (
        <Alert>
          <TriangleAlertIcon />
          <AlertTitle>Ít ảnh tham chiếu</AlertTitle>
          <AlertDescription>{warning}</AlertDescription>
        </Alert>
      )}

      {project.assets.length > 0 && <SelectionSummary assets={project.assets} />}

      <AssetSection title={KIND_LABEL.reference} kind="reference" assets={references} onMove={move} />
      {sideProfiles.length > 0 && (
        <AssetSection title={KIND_LABEL.side_profile} kind="side_profile" assets={sideProfiles} onMove={move} />
      )}
      {templates.length > 0 && (
        <AssetSection title={KIND_LABEL.template} kind="template" assets={templates} onMove={move} />
      )}
    </div>
  )
}

function SelectionSummary({ assets }: { assets: Asset[] }) {
  const select = useSelectAsset()
  const chosen = assets.filter((a) => a.selected)

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border p-4 text-sm">
      <p>
        Dùng <strong>{chosen.length}</strong>/{assets.length} ảnh để tạo nhân vật.
        {chosen.length === 0 && <span className="text-destructive"> Chọn ít nhất một ảnh.</span>}
      </p>
      <Button
        variant="outline"
        size="sm"
        disabled={select.isPending || chosen.length === assets.length}
        onClick={() => assets.filter((a) => !a.selected).forEach((a) => select.mutate({ assetId: a.id, selected: true }))}
      >
        Chọn tất cả
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={select.isPending || chosen.length === 0}
        onClick={() => chosen.forEach((a) => select.mutate({ assetId: a.id, selected: false }))}
      >
        Bỏ chọn tất cả
      </Button>
      {select.error && <p className="text-xs text-destructive">{select.error.message}</p>}
    </div>
  )
}

function AssetSection({
  title,
  kind,
  assets,
  onMove,
}: {
  title: string
  kind: AssetKind
  assets: Asset[]
  onMove: (kind: AssetKind, from: number, to: number) => void
}) {
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [overIndex, setOverIndex] = useState<number | null>(null)

  if (assets.length === 0) {
    return kind === 'reference' ? (
      <p className="rounded-xl border bg-card p-8 text-center text-sm text-muted-foreground">
        Chưa có ảnh tham chiếu nào.
      </p>
    ) : null
  }
  return (
    <section>
      <h2 className="mb-3 font-medium">
        {title} <span className="text-muted-foreground">({assets.length})</span>
        <span className="ml-2 text-sm font-normal text-muted-foreground">
          Kéo thả để đổi thứ tự. Ảnh #1 ảnh hưởng nhiều nhất tới trang phục và bố cục.
        </span>
      </h2>
      <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {assets.map((asset, index) => (
          <AssetTile
            key={asset.id}
            asset={asset}
            index={index}
            isFirst={index === 0}
            isLast={index === assets.length - 1}
            dragging={dragIndex === index}
            over={overIndex === index && dragIndex !== null && dragIndex !== index}
            onDragStart={() => setDragIndex(index)}
            onDragEnter={() => setOverIndex(index)}
            onDragEnd={() => { setDragIndex(null); setOverIndex(null) }}
            onDrop={() => {
              if (dragIndex !== null && dragIndex !== index) onMove(kind, dragIndex, index)
              setDragIndex(null)
              setOverIndex(null)
            }}
            onMove={(to) => onMove(kind, index, to)}
          />
        ))}
      </ul>
    </section>
  )
}

function AssetTile({
  asset,
  index,
  isFirst,
  isLast,
  onMove,
  dragging,
  over,
  onDragStart,
  onDragEnter,
  onDragEnd,
  onDrop,
}: {
  asset: Asset
  index: number
  isFirst: boolean
  isLast: boolean
  onMove: (to: number) => void
  dragging: boolean
  over: boolean
  onDragStart: () => void
  onDragEnter: () => void
  onDragEnd: () => void
  onDrop: () => void
}) {
  const remove = useDeleteAsset()
  const changeKind = useUpdateAssetKind()
  const select = useSelectAsset()
  const otherKind: AssetKind = asset.kind === 'reference' ? 'side_profile' : 'reference'
  const canSwapKind = asset.kind !== 'template'
  const busy = remove.isPending || changeKind.isPending || select.isPending

  return (
    <li
      draggable={!busy}
      onDragStart={(e) => { e.dataTransfer.effectAllowed = 'move'; onDragStart() }}
      onDragEnter={onDragEnter}
      onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move' }}
      onDragEnd={onDragEnd}
      onDrop={(e) => { e.preventDefault(); onDrop() }}
      className={`overflow-hidden rounded-xl border bg-card ${busy ? '' : 'cursor-grab active:cursor-grabbing'} ${
        dragging ? 'opacity-40' : ''} ${over ? 'ring-2 ring-primary' : ''} ${
        asset.selected ? '' : 'border-dashed opacity-60'}`}
    >
      <div className="relative aspect-square bg-muted">
        <img src={assetUrl(asset.id)} alt={asset.filename} className="absolute inset-0 size-full object-cover" loading="lazy" />
        <Badge className="absolute top-2 left-2">#{index + 1}</Badge>
        <span className="absolute top-2 right-2 rounded bg-background/90 p-1">
          <Checkbox
            id={`use-${asset.id}`}
            checked={asset.selected}
            disabled={busy}
            aria-label={`Dùng ${asset.filename} để tạo nhân vật`}
            onCheckedChange={(checked) => select.mutate({ assetId: asset.id, selected: checked === true })}
          />
        </span>
      </div>
      <div className="grid gap-2 p-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium" title={asset.filename}>
            {asset.filename}
          </p>
          <p className="text-xs text-muted-foreground">
            {asset.width}×{asset.height} · {formatBytes(asset.size)}
            {!asset.selected && <span className="block">Không dùng để tạo ảnh</span>}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="outline" size="icon-sm" aria-label="Chuyển lên trước" disabled={isFirst || busy} onClick={() => onMove(index - 1)}>
            <ArrowLeftIcon />
          </Button>
          <Button variant="outline" size="icon-sm" aria-label="Chuyển ra sau" disabled={isLast || busy} onClick={() => onMove(index + 1)}>
            <ArrowRightIcon />
          </Button>
          {canSwapKind && <Button
            variant="outline"
            size="icon-sm"
            aria-label={`Chuyển thành ${KIND_LABEL[otherKind].toLowerCase()}`}
            title={`Chuyển thành ${KIND_LABEL[otherKind].toLowerCase()}`}
            disabled={busy}
            onClick={() => changeKind.mutate({ assetId: asset.id, kind: otherKind })}
          >
            <RepeatIcon />
          </Button>}
          <Button
            variant="destructive"
            size="icon-sm"
            className="ml-auto"
            aria-label={`Xoá ${asset.filename}`}
            disabled={busy}
            onClick={() => remove.mutate(asset.id)}
          >
            <Trash2Icon />
          </Button>
        </div>
        {(remove.error || changeKind.error || select.error) && (
          <p className="text-xs text-destructive">{(remove.error ?? changeKind.error ?? select.error)?.message}</p>
        )}
      </div>
    </li>
  )
}
