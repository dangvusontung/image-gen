import { useState } from 'react'
import type { Concept } from '@/api/client'
import { useGenerationAction } from '@/components/GenerationUI'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import CopyPromptButton from '@/components/CopyPromptButton'
import { ErrorAlert } from '@/components/ErrorAlert'

export default function EditConceptPrompt({ concept, projectId, size, disabled }: {
  concept: Concept; projectId: string; size: string; disabled: boolean
}) {
  const [open, setOpen] = useState(false)
  const [prompt, setPrompt] = useState(concept.job.prompt)
  const action = useGenerationAction(projectId)
  return <>
    <Button size="sm" variant="outline" onClick={() => setOpen(true)}>Sửa prompt ô {concept.slot}</Button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-h-[90vh] overflow-auto sm:max-w-3xl">
        <DialogTitle>Prompt ô {concept.slot} · {concept.mood}</DialogTitle>
        <DialogDescription>Chỉnh prompt đầy đủ và tạo phiên bản mới. Ảnh hiện tại được giữ lại.</DialogDescription>
        <Textarea aria-label={`Prompt ô ${concept.slot}`} rows={12} value={prompt} onChange={e => setPrompt(e.target.value)} />
        <div className="flex flex-wrap gap-2">
          <CopyPromptButton text={prompt} />
          <Button disabled={disabled || action.isPending || !prompt.trim()} onClick={() => action.mutate({
            path: `/projects/${projectId}/concepts/${concept.id}/regenerate`, data: { prompt, size: size || null },
          }, { onSuccess: () => setOpen(false) })}>Tạo lại với prompt này</Button>
        </div>
        {action.error && <ErrorAlert error={action.error} title="Không tạo lại được" />}
      </DialogContent>
    </Dialog>
  </>
}
