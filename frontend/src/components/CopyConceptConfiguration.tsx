import { useImageSize } from '@/lib/imageSize'
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { request, useProjects, type ConceptProposal } from '@/api/client'
import { Button } from '@/components/ui/button'
import { ErrorAlert } from '@/components/ErrorAlert'

export default function CopyConceptConfiguration({ projectId, labels, onCopy }: {
  projectId: string
  labels: Record<string, string>
  onCopy: (edits: Record<number, Record<string, string>>) => void
}) {
  const projects = useProjects()
  const qc = useQueryClient()
  const [, setSize] = useImageSize(projectId)
  const [sourceId, setSourceId] = useState('')
  const [copied, setCopied] = useState(false)
  const source = useQuery({
    queryKey: ['copy-concept-configuration', sourceId],
    enabled: Boolean(sourceId),
    queryFn: () => request<ConceptProposal[]>(`/projects/${sourceId}/concept-proposals`),
  })
  const configuration = useQuery({
    queryKey: ['copy-project-configuration', sourceId], enabled: Boolean(sourceId),
    queryFn: () => request<{ provider: string; model: string; workflow_mode: string; preset_name: string | null; preset_steps: Record<string, { provider: string; model: string; size?: string }>; prompts: Record<string, string> }>(`/projects/${sourceId}/configuration`),
  })
  const copy = useMutation({
    mutationFn: () => request(`/projects/${projectId}/prompts/copy`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_project_id: sourceId, include_configuration: true, prompt_names: [] }),
    }),
    onSuccess: async () => {
      onCopy(Object.fromEntries(configurations.map(({ slot, fields }) => [slot, fields])))
      try { setSize(localStorage.getItem(`image-size:${sourceId}`) ?? '') } catch { setSize('') }
      setCopied(true)
      await qc.invalidateQueries()
    },
  })
  const [copiedPrompt, setCopiedPrompt] = useState('')
  const copyPrompt = useMutation({
    mutationFn: (name: string) => request(`/projects/${projectId}/prompts/copy`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_project_id: sourceId, prompt_names: [name] }),
    }),
    onSuccess: async (_, name) => { setCopiedPrompt(name); await qc.invalidateQueries({ queryKey: ['prompt', projectId] }) },
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
    <summary className="cursor-pointer font-semibold">Xem và chép cấu hình từ dự án khác</summary>
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
    {configuration.error && <ErrorAlert error={configuration.error} title="Không tải được cấu hình dự án" />}
    {configuration.data && <div className="space-y-2 rounded-lg bg-muted p-3 text-sm">
      <p>{configuration.data.provider} · {configuration.data.model}</p>
      <p>Quy trình: {configuration.data.workflow_mode}</p>
      {configuration.data.preset_name && <p>Preset: {configuration.data.preset_name}</p>}
      {Object.entries(configuration.data.preset_steps).map(([step, value]) => <p key={step}>{step}: {value.provider} · {value.model} · {value.size || 'mặc định'}</p>)}
      {Object.entries(configuration.data.prompts).map(([name, body]) => <details key={name}>
        <summary className="cursor-pointer">Prompt {name}</summary>
        <Button className="my-2" size="sm" disabled={copyPrompt.isPending} onClick={() => copyPrompt.mutate(name)}>Chép riêng prompt {name}</Button><p className="whitespace-pre-wrap break-words">{body}</p>
      </details>)}
    </div>}
    {copiedPrompt && <p role="status">Đã chép riêng prompt {copiedPrompt}.</p>}
    {copyPrompt.error && <ErrorAlert error={copyPrompt.error} title="Không chép được prompt" />}
    {copy.error && <ErrorAlert error={copy.error} title="Không chép được cấu hình" />}
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
      <p className="text-xs text-muted-foreground">Chép sẽ thay thế mô tả concept, provider/model, preset. Prompt được chép riêng bằng nút ở từng mục của dự án này. Ảnh đã tạo giữ nguyên.</p>
      <Button disabled={copy.isPending || !configuration.data || configuration.isError || source.isError} onClick={() => copy.mutate()}>
        Chép concept và cài đặt model
      </Button>
    </>}
    {copied && <p role="status" className="text-sm">Đã chép concept và cài đặt model. Có thể chỉnh thêm trước khi tạo ảnh.</p>}
  </details>
}
