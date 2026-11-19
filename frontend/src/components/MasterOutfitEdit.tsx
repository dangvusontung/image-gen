import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, assetUrl, request, type Asset, type ProjectDetail } from '@/api/client'
import { Button } from '@/components/ui/button'
import { ErrorAlert } from '@/components/ErrorAlert'

export default function MasterOutfitEdit({ project, masterId, masterAssetId, onClose }: { project: ProjectDetail; masterId: string; masterAssetId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [uploaded, setUploaded] = useState<Asset[]>([])
  const [sourceId, setSourceId] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const assets = [...project.assets, ...uploaded].filter((asset, index, all) => all.findIndex(row => row.id === asset.id) === index)
  const choose = (id: string) => { setSourceId(id); setConfirmed(false) }
  const upload = useMutation({ mutationFn: (file: File) => api.uploadAssets(project.id, [file], 'template'), onSuccess: rows => {
    setUploaded(previous => [...previous, ...rows]); choose(rows[0].id)
    qc.invalidateQueries({ queryKey: ['projects', project.id] })
  } })
  const generate = useMutation({ mutationFn: () => request(`/projects/${project.id}/master/${masterId}/outfit`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ outfit_reference_asset_id: sourceId, confirmed: true }),
  }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['workflow', project.id] }); onClose() } })
  const busy = upload.isPending || generate.isPending
  return <section className="space-y-3 rounded-xl border p-4" aria-label="Đổi outfit Master" onPaste={event => {
    const image = Array.from(event.clipboardData.files).find(file => file.type.startsWith('image/'))
    if (image && !busy) { event.preventDefault(); upload.mutate(image) }
  }} tabIndex={0}>
    <h4 className="font-semibold">Đổi outfit · tùy chọn</h4>
    <p className="text-sm text-muted-foreground">Giữ Master hiện tại, chỉ thay trang phục. Chọn ảnh bên dưới hoặc click vào đây rồi paste ảnh. Bản mới cần được duyệt riêng.</p>
    <img src={assetUrl(masterAssetId)} alt="Master nguồn" className="h-36 object-contain" />
    <label className="block text-sm">Chọn ảnh outfit mới <input aria-label="Ảnh outfit mới" type="file" accept="image/*" disabled={busy || !project.rights_confirmed} onChange={event => {
      const file = event.target.files?.[0]; if (file) upload.mutate(file); event.target.value = ''
    }} /></label>
    <div className="flex gap-2 overflow-x-auto">{assets.map(asset => <button key={asset.id} type="button" disabled={busy} aria-label={`Chọn outfit ${asset.filename}`} aria-pressed={sourceId === asset.id} onClick={() => choose(asset.id)} className={`w-24 shrink-0 rounded-lg border-2 p-1 ${sourceId === asset.id ? 'border-primary' : 'border-transparent'}`}>
      <img src={assetUrl(asset.id)} alt={asset.filename} className="h-24 w-full object-contain" /><span className="block truncate text-xs">{asset.filename}</span>
    </button>)}</div>
    {sourceId && <img src={assetUrl(sourceId)} alt="Outfit được chọn" className="h-32 object-contain" />}
    {upload.isPending && <p role="status">Đang tải ảnh…</p>}
    {upload.error && <ErrorAlert error={upload.error} title="Không tải được ảnh" />}
    {generate.error && <ErrorAlert error={generate.error} title="Không đổi được outfit" />}
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={confirmed} disabled={busy} onChange={event => setConfirmed(event.target.checked)} />Xác nhận tạo 1 Master mới và gửi 2 ảnh tới nhà cung cấp; có thể phát sinh phí.</label>
    <div className="flex gap-2"><Button disabled={busy || !sourceId || !confirmed || !project.rights_confirmed} onClick={() => generate.mutate()}>{generate.isPending ? 'Đang tạo…' : 'Tạo Master với outfit mới'}</Button><Button variant="outline" disabled={busy} onClick={onClose}>Đóng</Button></div>
  </section>
}
