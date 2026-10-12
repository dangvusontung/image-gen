import { useState } from 'react'
import { ChevronDownIcon, SettingsIcon, StarIcon } from 'lucide-react'
import { generationProject } from '@/lib/generationPolicy'
import { useProviders, useUpdateProject, type ProjectDetail } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'
import { useFavouriteModels } from '@/lib/favourites'
import { useImageSize } from '@/lib/imageSize'
import { defaultGenerationSize } from '@/lib/generationPolicy'
import { groupByGeneration } from '@/lib/providers'

/** Always-reachable provider/model switcher, so it is not lost above the fold on long steps. */
export default function PinnedModelSwitcher({ project }: { project: ProjectDetail }) {
  const [open, setOpen] = useState(false)
  const { data: providers } = useProviders()
  const update = useUpdateProject(project.id)
  const { favourites, isFavourite, toggle } = useFavouriteModels()
  const [size, setSize] = useImageSize(project.id)

  if (!providers) return null
  // Hybrid modes pick the model per step, so there is nothing here to switch.
  const hybrid = Boolean(project.workflow_mode && project.workflow_mode !== 'manual')
  const draft = generationProject(project, 'draft')
  const provider = providers.find((p) => p.name === draft.provider)
  const model = provider?.models.find((m) => m.id === draft.model)
  const starred = providers.flatMap((p) =>
    p.models.filter((m) => isFavourite(p.name, m.id)).map((m) => ({ provider: p, model: m })),
  )
  const generations = groupByGeneration(provider?.models ?? [])

  return (
    <aside className={`fixed bottom-4 left-4 z-40 rounded-xl border bg-popover text-sm shadow-lg ${open ? 'w-72' : 'max-w-56'}`}>
      <button
        type="button"
        className="flex w-full items-center gap-2 p-3 text-left"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <SettingsIcon className="size-4 shrink-0" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{model?.display_name ?? draft.model}</span>
          <span className="block truncate text-xs text-muted-foreground">
            {hybrid ? 'Quy trình tiết kiệm · model theo từng bước' : `${provider?.display_name ?? draft.provider}${size ? ` · ${size}` : ''}`}
          </span>
        </span>
        <ChevronDownIcon className={`size-4 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
      </button>

      {open && <div className="space-y-3 border-t p-3">
        {hybrid && <p className="text-xs text-muted-foreground">
          Quy trình tiết kiệm tự chọn model cho mỗi bước. Chuyển sang “Thủ công” ở đầu trang để đổi tay.
        </p>}

        {starred.length > 0 && <div className="space-y-1">
          <p className="text-xs font-medium">Yêu thích</p>
          {starred.map(({ provider: p, model: m }) => (
            <div key={`${p.name}/${m.id}`} className="flex items-center gap-1">
              <Button
                variant={draft.provider === p.name && draft.model === m.id ? 'default' : 'outline'}
                size="sm"
                className="min-w-0 flex-1 justify-start"
                disabled={hybrid || update.isPending || !p.enabled}
                onClick={() => update.mutate({ provider: p.name, model: m.id })}
              >
                <span className="truncate">{m.display_name}</span>
              </Button>
              <Button variant="ghost" size="icon-sm" aria-label={`Bỏ yêu thích ${m.id}`} onClick={() => toggle(p.name, m.id)}>
                <StarIcon className="fill-current text-amber-500" />
              </Button>
            </div>
          ))}
        </div>}

        {!hybrid && <>
          <label className="grid gap-1 text-xs">Nhà cung cấp
            <select
              aria-label="Nhà cung cấp (ghim)"
              className="rounded border p-2 text-sm"
              value={project.provider}
              disabled={update.isPending}
              onChange={(e) => update.mutate({ provider: e.target.value })}
            >
              {providers.map((p) => <option key={p.name} value={p.name} disabled={!p.enabled}>{p.display_name}</option>)}
            </select>
          </label>
          <label className="grid gap-1 text-xs">Model
            <select
              aria-label="Model (ghim)"
              className="rounded border p-2 text-sm"
              value={project.model}
              disabled={update.isPending}
              onChange={(e) => update.mutate({ model: e.target.value })}
            >
              {generations.map(({ generation, models }) => (
                <optgroup key={generation.key} label={generation.label}>
                  {models.map((m) => <option key={m.id} value={m.id}>{m.display_name} — {m.id}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          {!!model?.sizes?.length && <label className="grid gap-1 text-xs">Kích thước ảnh
            <select
              aria-label="Kích thước ảnh (ghim)"
              className="rounded border p-2 text-sm"
              value={size}
              onChange={(e) => setSize(e.target.value)}
            >
              <option value="">Mặc định ({defaultGenerationSize(project, model.default_size)})</option>
              {model.sizes.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>}
          {model && <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>≤{model.max_reference_images} ảnh tham chiếu</span>
            <Button
              variant="ghost"
              size="sm"
              aria-label={`${isFavourite(draft.provider, draft.model) ? 'Bỏ yêu thích' : 'Đánh dấu yêu thích'} ${draft.model}`}
              onClick={() => toggle(draft.provider, draft.model)}
            >
              <StarIcon className={isFavourite(draft.provider, draft.model) ? 'fill-current text-amber-500' : ''} />
              {isFavourite(draft.provider, draft.model) ? 'Bỏ ghim' : 'Ghim model này'}
            </Button>
          </div>}
        </>}
        {update.error && <ErrorAlert error={update.error} title="Không đổi được model" />}
        {favourites.length === 0 && <p className="text-xs text-muted-foreground">
          Đánh dấu sao ở trang “Nhà cung cấp & model” để đổi nhanh giữa các model hay dùng.
        </p>}
      </div>}
    </aside>
  )
}
