import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { assetUrl, request } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { ErrorAlert } from '@/components/ErrorAlert'

interface TrashItem {
  kind: 'job' | 'asset'; id: string; project_name: string; title: string
  asset_ids: string[]; error_message: string | null
}

export function useTrashAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ path, method = 'POST' }: { path: string; method?: string }) => request(path, { method }),
    onSuccess: () => { void qc.invalidateQueries() },
  })
}

export function TrashImageButton({ assetId, onTrashed }: { assetId: string; onTrashed?: () => void }) {
  const action = useTrashAction()
  return <div>
    <Button variant="outline" size="sm" disabled={action.isPending} onClick={() => action.mutate({ path: `/trash/assets/${assetId}` }, { onSuccess: onTrashed })}>Chuyển ảnh vào Thùng rác</Button>
    {action.error && <ErrorAlert title="Không chuyển được ảnh" error={action.error} />}
  </div>
}

export default function Trash() {
  const [open, setOpen] = useState(false)
  const [confirm, setConfirm] = useState<TrashItem | null>(null)
  const items = useQuery({ queryKey: ['trash'], queryFn: () => request<TrashItem[]>('/trash'), enabled: open })
  const action = useTrashAction()
  return <>
    <Button className="fixed bottom-4 right-4 z-40 shadow-lg" size="sm" variant="outline" onClick={() => setOpen(true)}>Thùng rác</Button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-h-[90vh] overflow-auto sm:max-w-3xl">
        <DialogTitle>Thùng rác</DialogTitle>
        <DialogDescription>Run và ảnh ở đây được giữ lại cho đến khi bạn xoá vĩnh viễn. Khôi phục để đưa về danh sách cũ.</DialogDescription>
        {items.error && <ErrorAlert title="Không tải được Thùng rác" error={items.error} />}
        {action.error && <ErrorAlert title="Không thực hiện được" error={action.error} />}
        {items.isPending && <p>Đang tải…</p>}
        {items.data?.length === 0 && <p>Thùng rác trống.</p>}
        {items.data?.map(item => <article key={`${item.kind}/${item.id}`} className="space-y-2 rounded-lg border p-3">
          <p className="font-medium">{item.project_name} · {item.kind === 'job' ? 'Run' : 'Ảnh'}</p>
          <p className="text-sm">{item.title}</p>
          {item.error_message && <p className="text-sm text-destructive">{item.error_message}</p>}
          <div className="flex flex-wrap gap-2">{item.asset_ids.map(id => <img key={id} src={assetUrl(id)} alt={item.title} className="h-24 w-20 rounded object-contain" />)}</div>
          <div className="flex gap-2">
            <Button variant="outline" disabled={action.isPending} onClick={() => action.mutate({ path: `/trash/${item.kind}/${item.id}/restore` })}>Khôi phục</Button>
            <Button variant="destructive" disabled={action.isPending} onClick={() => setConfirm(item)}>Xoá vĩnh viễn</Button>
          </div>
        </article>)}
      </DialogContent>
    </Dialog>
    <Dialog open={!!confirm} onOpenChange={value => { if (!value) setConfirm(null) }}>
      <DialogContent>
        <DialogTitle>Xoá vĩnh viễn?</DialogTitle>
        <DialogDescription>{confirm?.title} — ảnh sẽ bị xoá khỏi lưu trữ và không thể khôi phục.</DialogDescription>
        <Button variant="outline" disabled={action.isPending} onClick={() => setConfirm(null)}>Giữ lại</Button>
        <Button variant="destructive" disabled={action.isPending} onClick={() => { if (confirm) action.mutate({ path: `/trash/${confirm.kind}/${confirm.id}`, method: 'DELETE' }, { onSuccess: () => setConfirm(null) }) }}>Xoá vĩnh viễn</Button>
        {action.error && <ErrorAlert title="Không xoá được" error={action.error} />}
      </DialogContent>
    </Dialog>
  </>
}
