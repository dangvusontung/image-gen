import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, assetUrl, request, type Asset, type ProjectDetail } from '@/api/client'
import { Button } from '@/components/ui/button'
import { ErrorAlert } from '@/components/ErrorAlert'

export default function CloneConcept({ project, onQueued }: { project: ProjectDetail; onQueued: (id: string) => void }) {
  const qc = useQueryClient()
  const workflow = useQuery({ queryKey: ['workflow', project.id], queryFn: () => request<{ approved_master_id: string | null; masters: { id: string; round: number; variant: number; job: { status: string; output_asset_ids: string[] } }[] }>(`/projects/${project.id}/workflow`) })
  const masters = workflow.data?.masters?.filter(row => row.job.status === 'succeeded') ?? []
  const [masterId, setMasterId] = useState('')
  const chosenMaster = masters.find(row => row.id === (masterId || workflow.data?.approved_master_id)) ?? (!masterId ? masters[0] : undefined)
  const [referenceId, setReferenceId] = useState('')
  const [uploaded, setUploaded] = useState<Asset[]>([])
  const [keepOutfit, setKeepOutfit] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [queued, setQueued] = useState(false)
  const reset = () => { setConfirmed(false); setQueued(false) }
  const upload = useMutation({ mutationFn: (file: File) => api.uploadAssets(project.id, [file], 'template'), onSuccess: rows => {
    setUploaded(previous => [...previous, ...rows]); setReferenceId(rows[0].id); reset()
    qc.invalidateQueries({ queryKey: ['projects', project.id] })
  } })
  const generate = useMutation({ mutationFn: () => request<{ concept_ids: string[] }>(`/projects/${project.id}/concepts/clone`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ master_version_id: chosenMaster?.id, reference_asset_id: referenceId, keep_master_outfit: keepOutfit, confirmed: true }),
  }), onSuccess: result => {
    setQueued(true); qc.invalidateQueries({ queryKey: ['concepts', project.id] }); qc.invalidateQueries({ queryKey: ['gallery'] }); onQueued(result.concept_ids[0])
  } })
  const busy = upload.isPending || generate.isPending
  return <details className="space-y-3 rounded-xl border p-4"><summary className="cursor-pointer font-semibold">Clone concept từ ảnh</summary>
    <div tabIndex={0} className="space-y-3" onPaste={event => {
      const file = Array.from(event.clipboardData.files).find(item => item.type.startsWith('image/'))
      if (file && !busy && project.rights_confirmed) { event.preventDefault(); upload.mutate(file) }
    }}>
      <p className="text-sm text-muted-foreground">Master giữ nhận diện và phong cách hình ảnh. Ảnh refer cung cấp pose, bố cục, bối cảnh và ánh sáng. Chọn ảnh có sẵn hoặc paste/upload ảnh mới.</p>
      <label className="block">Master <select aria-label="Master để clone concept" className="rounded border p-2" disabled={busy} value={chosenMaster?.id ?? ''} onChange={event => { setMasterId(event.target.value); reset() }}>
        {!masters.length && <option value="">Chưa có Master</option>}{masters.map(row => <option key={row.id} value={row.id}>Master {row.round}/{row.variant}{workflow.data?.approved_master_id === row.id ? ' · Đã duyệt' : ''}</option>)}
      </select></label>
      <div className="flex gap-3">{chosenMaster?.job.output_asset_ids[0] && <img src={assetUrl(chosenMaster.job.output_asset_ids[0])} alt="Master clone" className="h-36 w-36 object-contain" />}{referenceId && <img src={assetUrl(referenceId)} alt="Refer clone" className="h-36 w-36 object-contain" />}</div>
      <label className="block">Ảnh refer mới <input aria-label="Ảnh refer clone mới" type="file" accept="image/*" disabled={busy || !project.rights_confirmed} onChange={event => { const file = event.target.files?.[0]; if (file) upload.mutate(file); event.target.value = '' }} /></label>
      <div className="flex gap-2 overflow-x-auto">{[...(project.assets ?? []), ...uploaded].filter((asset, index, rows) => rows.findIndex(row => row.id === asset.id) === index).map(asset => <button key={asset.id} type="button" aria-label={`Refer clone ${asset.filename}`} aria-pressed={referenceId === asset.id} disabled={busy} onClick={() => { setReferenceId(asset.id); reset() }} className={`w-24 shrink-0 rounded border-2 p-1 ${referenceId === asset.id ? 'border-primary' : 'border-transparent'}`}><img src={assetUrl(asset.id)} alt={asset.filename} className="h-24 w-full object-contain" /></button>)}</div>
      <label className="flex gap-2"><input type="checkbox" checked={keepOutfit} disabled={busy} onChange={event => { setKeepOutfit(event.target.checked); reset() }} />Giữ outfit Master (bỏ chọn để lấy outfit từ ảnh refer)</label>
      <label className="flex gap-2 text-sm"><input type="checkbox" checked={confirmed} disabled={busy} onChange={event => setConfirmed(event.target.checked)} />Xác nhận tạo 1 concept, gửi 2 ảnh tới nhà cung cấp; có thể phát sinh phí.</label>
      {workflow.error && <ErrorAlert error={workflow.error} title="Không tải được Master" />}
      {upload.isPending && <p role="status">Đang tải ảnh refer…</p>}
      {upload.error && <ErrorAlert error={upload.error} title="Không tải được ảnh refer" />}
      {generate.error && <ErrorAlert error={generate.error} title="Không clone được concept" />}
      {queued && <p role="status">Đã gửi tạo clone trong batch mới.</p>}
      <Button disabled={busy || queued || !chosenMaster || !referenceId || !confirmed || !project.rights_confirmed} onClick={() => generate.mutate()}>{generate.isPending ? 'Đang gửi…' : 'Tạo clone concept'}</Button>
    </div>
  </details>
}
