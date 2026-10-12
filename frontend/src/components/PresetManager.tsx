import { useState } from 'react'
import { PlusIcon, Trash2Icon } from 'lucide-react'
import { useDeletePreset, usePresets, useProviders, useSavePreset,
         type Preset, type PresetStep, type WorkflowStep } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { groupByGeneration } from '@/lib/providers'

const STEPS: { key: WorkflowStep; label: string }[] = [
  { key: 'master', label: '2. Nhân vật gốc' },
  { key: 'turnaround', label: '3. Turnaround' },
  { key: 'concept', label: '4. Concept' },
  { key: 'enhance', label: '5. Nâng cấp' },
]

type Draft = { id?: string; name: string; steps: Partial<Record<WorkflowStep, PresetStep>> }

/** Build a per-step provider/model/size preset once, then reuse it on any project. */
export default function PresetManager() {
  const { data: presets } = usePresets()
  const { data: providers } = useProviders()
  const save = useSavePreset()
  const remove = useDeletePreset()
  const [draft, setDraft] = useState<Draft | null>(null)

  const usable = (providers ?? []).filter((p) => p.selectable && p.key_configured)
  const setStep = (step: WorkflowStep, value: PresetStep | undefined) =>
    setDraft((d) => (d ? { ...d, steps: { ...d.steps, [step]: value } } : d))

  const edit = (preset?: Preset) =>
    setDraft(preset ? { id: preset.id, name: preset.name, steps: { ...preset.steps } } : { name: '', steps: {} })

  return (
    <section className="grid gap-3 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-semibold">Bộ cấu hình theo bước</h2>
          <p className="text-sm text-muted-foreground">
            Chọn model và kích thước riêng cho từng bước, dùng lại cho mọi dự án. Bước không đặt sẽ theo cài đặt của dự án.
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={() => edit()}><PlusIcon /> Tạo bộ mới</Button>
      </div>

      {!presets?.length && !draft && <p className="text-sm text-muted-foreground">Chưa có bộ cấu hình nào.</p>}
      <ul className="grid gap-2">
        {presets?.map((preset) => (
          <li key={preset.id} className="flex flex-wrap items-center gap-3 rounded-lg border p-3 text-sm">
            <span className="font-medium">{preset.name}</span>
            <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
              {STEPS.filter((s) => preset.steps[s.key])
                .map((s) => `${s.label}: ${preset.steps[s.key]!.model}${preset.steps[s.key]!.size ? ` · ${preset.steps[s.key]!.size}` : ''}`)
                .join(' | ') || 'Chưa đặt bước nào'}
            </span>
            <Button size="sm" variant="outline" onClick={() => edit(preset)}>Sửa</Button>
            <Button size="sm" variant="ghost" aria-label={`Xoá bộ ${preset.name}`}
              onClick={() => { if (confirm(`Xoá bộ cấu hình "${preset.name}"?`)) remove.mutate(preset.id) }}>
              <Trash2Icon />
            </Button>
          </li>
        ))}
      </ul>

      {draft && <div className="grid gap-3 rounded-lg border p-3">
        <label className="grid gap-1 text-sm">Tên bộ cấu hình
          <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            placeholder="Ví dụ: Gemini nháp, FLUX hoàn thiện" />
        </label>
        {STEPS.map(({ key, label }) => {
          const step = draft.steps[key]
          const provider = usable.find((p) => p.name === step?.provider)
          const model = provider?.models.find((m) => m.id === step?.model)
          return (
            <div key={key} className="grid gap-2 border-t pt-2 sm:grid-cols-[10rem_1fr_1fr_8rem] sm:items-center">
              <span className="text-sm font-medium">{label}</span>
              <select aria-label={`Nhà cung cấp cho ${label}`} className="rounded border p-2 text-sm"
                value={step?.provider ?? ''}
                onChange={(e) => {
                  const next = usable.find((p) => p.name === e.target.value)
                  setStep(key, next ? { provider: next.name, model: next.models[0]?.id ?? '', size: null } : undefined)
                }}>
                <option value="">Theo cài đặt dự án</option>
                {usable.map((p) => <option key={p.name} value={p.name}>{p.display_name}</option>)}
              </select>
              <select aria-label={`Model cho ${label}`} className="rounded border p-2 text-sm" disabled={!provider}
                value={step?.model ?? ''}
                onChange={(e) => step && setStep(key, { ...step, model: e.target.value, size: null })}>
                {groupByGeneration(provider?.models ?? []).map(({ generation, models }) => (
                  <optgroup key={generation.key} label={generation.label}>
                    {models.map((m) => <option key={m.id} value={m.id}>{m.display_name} — {m.id}</option>)}
                  </optgroup>
                ))}
              </select>
              <select aria-label={`Kích thước cho ${label}`} className="rounded border p-2 text-sm"
                disabled={!model?.sizes?.length} value={step?.size ?? ''}
                onChange={(e) => step && setStep(key, { ...step, size: e.target.value || null })}>
                <option value="">Mặc định</option>
                {model?.sizes?.map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
          )
        })}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" disabled={!draft.name.trim() || save.isPending}
            onClick={() => save.mutate(draft, { onSuccess: () => setDraft(null) })}>Lưu bộ cấu hình</Button>
          <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>Huỷ</Button>
        </div>
      </div>}
      {save.error && <ErrorAlert error={save.error} title="Không lưu được bộ cấu hình" />}
      {remove.error && <ErrorAlert error={remove.error} title="Không xoá được bộ cấu hình" />}
    </section>
  )
}
