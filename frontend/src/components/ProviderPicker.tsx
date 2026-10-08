import { TriangleAlertIcon } from 'lucide-react'
import { useProviders, useUpdateProject, type ProjectDetail } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { formatUsd, providerStatus, referenceLimitWarning } from '@/lib/providers'

export default function ProviderPicker({ project }: { project: ProjectDetail }) {
  const { data: providers } = useProviders()
  const update = useUpdateProject(project.id)

  if (!providers) return null
  const provider = providers.find((p) => p.name === project.provider)
  const model = provider?.models.find((m) => m.id === project.model)
  const referenceCount = project.assets.filter((a) => a.kind === 'reference').length
  const warning = referenceLimitWarning(model, referenceCount)

  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1">
          <Label htmlFor="provider-select" className="text-xs text-muted-foreground">
            Nhà cung cấp
          </Label>
          <Select
            value={project.provider}
            onValueChange={(value) => update.mutate({ provider: value })}
            disabled={update.isPending}
          >
            <SelectTrigger id="provider-select" className="w-64">
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
            <SelectTrigger id="model-select" className="w-72">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {provider?.models.map((m) => (
                <SelectItem key={m.id} value={m.id}>
                  {m.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {model && (
          <p className="pb-1.5 text-xs text-muted-foreground">
            ≤{model.max_reference_images} ảnh tham chiếu · {formatUsd(model.price_per_image_usd)}/ảnh
          </p>
        )}
      </div>
      {provider && !provider.enabled && (
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
