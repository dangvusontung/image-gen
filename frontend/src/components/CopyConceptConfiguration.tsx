import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { request, useProjects, type ConceptProposal } from '@/api/client'
import { Button } from '@/components/ui/button'
import { ErrorAlert } from '@/components/ErrorAlert'

export default function CopyConceptConfiguration({ projectId, labels, onCopy }: {
  projectId: string
  labels: Record<string, string>
  onCopy: (edits: Record<number, Record<string, string>>) => void
}) {
  const projects = useProjects()
  const [sourceId, setSourceId] = useState('')
  const [copied, setCopied] = useState(false)
  const source = useQuery({
    queryKey: ['copy-concept-configuration', sourceId],
    enabled: Boolean(sourceId),
    queryFn: () => request<ConceptProposal[]>(`/projects/${sourceId}/concept-proposals`),
  })
  const configurations = useMemo(() => {
    let drafts: Record<number, Record<string, string>> = {}
    try { drafts = JSON.parse(localStorage.getItem(`concept-edits:${sourceId}`) || '{}') } catch { /* no saved edits */ }
    return (source.data ?? []).map(concept => {
      const saved = drafts?.[concept.slot]
      const fields = Object.fromEntries(Object.entries(saved ?? {}).filter(([, value]) => typeof value === 'string'))
      return { slot: concept.slot, fields: { ...concept.brief, title: concept.title, ...fields } }
    })
  }, [source.data, sourceId])

  return <details className="space-y-3 rounded-xl border p-4">
    <summary className="cursor-pointer font-semibold">Xem và chép cấu hình concept từ dự án khác</summary>
    <label className="grid gap-1 text-sm">Dự án nguồn
      <select aria-label="Dự án nguồn cho cấu hình concept" className="max-w-full rounded border p-2"
        value={sourceId} onChange={e => { setSourceId(e.target.value); setCopied(false) }}>
        <option value="">Chọn dự án…</option>
        {(projects.data ?? []).filter(project => project.id !== projectId).map(project =>
          <option key={project.id} value={project.id}>{project.name}</option>)}
      </select>
    </label>
    {projects.error && <ErrorAlert error={projects.error} title="Không tải được dự án" />}
    {sourceId && source.isPending && <p className="text-sm">Đang tải cấu hình…</p>}
    {source.error && <ErrorAlert error={source.error} title="Không tải được cấu hình concept" />}
    {sourceId && !source.isPending && !source.error && !configurations.length && <p>Chưa có cấu hình concept.</p>}
    {configurations.length > 0 && <>
      <div className="max-h-96 space-y-2 overflow-y-auto">
        {configurations.map(({ slot, fields }) => <details key={slot} className="rounded-lg border p-3 text-sm">
          <summary className="cursor-pointer font-medium">{slot}. {fields.title}</summary>
          <dl className="mt-2 space-y-1">
            {Object.entries(fields).filter(([field]) => field !== 'title').map(([field, value]) =>
              <div key={field}><dt className="inline font-medium">{labels[field] ?? field}: </dt><dd className="inline break-words">{value}</dd></div>)}
          </dl>
        </details>)}
      </div>
      <p className="text-xs text-muted-foreground">Chép sẽ thay thế mô tả concept đang chỉnh ở dự án này. Ảnh đã tạo giữ nguyên.</p>
      <Button onClick={() => { onCopy(Object.fromEntries(configurations.map(({ slot, fields }) => [slot, fields]))); setCopied(true) }}>
        Chép {configurations.length} concept vào dự án này
      </Button>
    </>}
    {copied && <p role="status" className="text-sm">Đã chép cấu hình concept. Có thể chỉnh thêm trước khi tạo ảnh.</p>}
  </details>
}
