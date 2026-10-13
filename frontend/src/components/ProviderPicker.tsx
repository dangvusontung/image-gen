import { generationProject } from '@/lib/generationPolicy'
import { TriangleAlertIcon } from 'lucide-react'
import { useCopyPrompts, usePresets, useProjects, useProviders, useUpdateProject, type ProjectDetail } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@/components/ui/select'
import { formatUsd, groupByGeneration, providerStatus, referenceLimitWarning } from '@/lib/providers'

export default function ProviderPicker({ project }: { project: ProjectDetail }) {
  const { data: providers } = useProviders()
  const { data: projects } = useProjects()
  const update = useUpdateProject(project.id)
  const copyPrompts = useCopyPrompts(project.id)
  const others = (projects ?? []).filter((p) => p.id !== project.id)
  const { data: presets } = usePresets()
  const preset = presets?.find((p) => p.id === project.preset_id)

  if (!providers) return null
  const draft = generationProject(project, 'draft')
  const provider = providers.find((p) => p.name === draft.provider)
  const model = provider?.models.find((m) => m.id === draft.model)
  const referenceCount = project.assets.length
  const warning = referenceLimitWarning(model, referenceCount)
  const modelGenerations = groupByGeneration(provider?.models ?? [])

  return (
    <div className="grid gap-2">
      {!!presets?.length && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <label>
            Bộ cấu hình theo bước
            <select
              aria-label="Bộ cấu hình theo bước"
              className="max-w-full rounded border p-2"
              value={project.preset_id ?? ''}
              disabled={update.isPending}
              onChange={(e) => update.mutate({ preset_id: e.target.value || null })}
            >
              <option value="">Không dùng · theo cài đặt dự án</option>
              {presets.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          {preset && <span className="text-xs text-muted-foreground">
            Quyết định model cho: {Object.keys(preset.steps).join(', ') || 'chưa bước nào'}
          </span>}
        </div>
      )}
      {others.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <label>
            Chép prompt concept từ dự án
            <select
              aria-label="Chép prompt concept từ dự án"
              className="max-w-full rounded border p-2"
              value=""
              disabled={copyPrompts.isPending}
              onChange={(e) => { if (e.target.value) copyPrompts.mutate(e.target.value) }}
            >
              <option value="">Chọn dự án…</option>
              {others.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          {copyPrompts.isSuccess && <span role="status" className="text-emerald-700">Đã chép prompt sang dự án này.</span>}
          {copyPrompts.error && <ErrorAlert error={copyPrompts.error} title="Không chép được prompt" />}
        </div>
      )}
      <label className="grid gap-1 text-sm">Quy trình tạo ảnh
        <select aria-label="Quy trình tạo ảnh" className="w-full max-w-lg rounded border p-2" value={project.workflow_mode ?? 'manual'} disabled={update.isPending}
          onChange={e => update.mutate({ workflow_mode: e.target.value as ProjectDetail['workflow_mode'] })}>
          <option value="manual">Thủ công · một nhà cung cấp cho mọi bước</option>
          <option value="hybrid">Tiết kiệm · Gemini 1K → FLUX.2 Pro</option>
          <option value="hybrid_gemini">Tiết kiệm · Gemini 1K, hoàn thiện bằng Gemini</option>
        </select>
      </label>
      {project.workflow_mode && project.workflow_mode !== 'manual' && <div className="rounded border p-3 text-sm space-y-1">
        <p>Master, 6 góc và 9 concept: Gemini Nano Banana 2.1 ở 1K. Duyệt master trước khi tiếp tục.</p>
        <p>Nâng cấp: {project.workflow_mode === 'hybrid' ? 'FLUX.2 Pro ở 1MP' : 'Gemini Nano Banana 2.1 ở 1K'} · master + concept đã chọn + một góc phù hợp.</p>
        <p>Chi phí ước tính hiển thị ở từng bước; Gemini chưa gồm token đầu vào/văn bản. Nếu FLUX làm thay đổi khuôn mặt, chọn hoàn thiện bằng Gemini.</p>
        {['gemini', ...(project.workflow_mode === 'hybrid' ? ['bfl'] : [])].map(name => {
          const item = providers.find(p => p.name === name)
          return item && !item.enabled ? <p key={name} className="text-destructive">{item.display_name}: {providerStatus(item).label}. Cấu hình API key trong phần nhà cung cấp.</p> : null
        })}
      </div>}
      {(!project.workflow_mode || project.workflow_mode === 'manual') && <div className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1">
          <Label htmlFor="provider-select" className="text-xs text-muted-foreground">
            Nhà cung cấp
          </Label>
          <Select
            value={project.provider}
            onValueChange={(value) => update.mutate({ provider: value })}
            disabled={update.isPending}
          >
            <SelectTrigger id="provider-select" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {providers.map((p) => (
                <SelectItem key={p.name} value={p.name} disabled={!p.enabled}>
                  {p.display_name}
                  {!p.enabled && <span className="text-muted-foreground"> — {providerStatus(p).label}</span>}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1">
          <Label htmlFor="model-select" className="text-xs text-muted-foreground">
            Model
          </Label>
          <Select value={project.model} onValueChange={(value) => update.mutate({ model: value })} disabled={update.isPending}>
            <SelectTrigger id="model-select" className="w-full min-w-0">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {modelGenerations.map(({ generation, models }) => (
                <SelectGroup key={generation.key}>
                  {modelGenerations.length > 1 && <SelectLabel>{generation.label}</SelectLabel>}
                  {models.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      {/* Several models can share a display name, so the id is what tells them apart. */}
                      <span className="truncate">{m.display_name}</span>
                      <code className="ml-2 shrink-0 text-xs text-muted-foreground">{m.id}</code>
                    </SelectItem>
                  ))}
                </SelectGroup>
              ))}
            </SelectContent>
          </Select>
        </div>
        {model && (
          <p className="pb-1.5 text-xs text-muted-foreground">
            ≤{model.max_reference_images} ảnh tham chiếu · {formatUsd(model.price_per_image_usd)}/ảnh
          </p>
        )}
      </div>}
      {(!project.workflow_mode || project.workflow_mode === 'manual') && provider && !provider.enabled && (
        <p className="text-xs text-destructive">
          {provider.display_name}: {providerStatus(provider).label}. Các bước tạo ảnh sẽ báo lỗi cho tới khi cấu hình xong.
        </p>
      )}
      {warning && (
        <Alert>
          <TriangleAlertIcon />
          <AlertDescription>{warning}</AlertDescription>
        </Alert>
      )}
      {update.error && <ErrorAlert title="Không đổi được model" error={update.error} />}
    </div>
  )
}
