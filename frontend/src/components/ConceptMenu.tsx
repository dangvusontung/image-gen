import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { request } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'

export interface ConceptChoices {
  style: string; outfit: string; top: string; scene: string; lighting: string
  custom_outfit: string; custom_scene: string; activity: string
}
const defaults: ConceptChoices = { style: 'glamour', outfit: 'denim_mix', top: 'auto', scene: 'auto', lighting: 'auto', custom_outfit: '', custom_scene: '', activity: '' }

export function useConceptChoices(projectId: string) {
  const key = `concept-choices:${projectId}`
  const [choices, setChoices] = useState<ConceptChoices>(() => {
    try { return { ...defaults, ...JSON.parse(localStorage.getItem(key) || '{}') } } catch { return defaults }
  })
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(choices)) } catch { /* Browser storage may be unavailable. */ } }, [key, choices])
  return [choices, setChoices] as const
}

export function ConceptMenu({ projectId, choices, onChange }: { projectId: string; choices: ConceptChoices; onChange: (choices: ConceptChoices) => void }) {
  const menu = useQuery({ queryKey: ['concept-options', projectId], queryFn: () => request<Record<string, [string, string][]>>(`/projects/${projectId}/concept-options`) })
  const change = (key: keyof ConceptChoices, value: string) => onChange({ ...choices, [key]: value })
  return <fieldset className="space-y-4 rounded-xl border p-4">
    <legend className="px-2 font-semibold">Chọn trang phục và bối cảnh</legend>
    <p className="text-sm text-muted-foreground">Áp dụng cho ảnh tạo mới và nút tạo lại ô. Có thể tạo nhiều đợt với lựa chọn khác nhau; mỗi ô vẫn có biểu cảm và góc máy riêng.</p>
    {menu.error && <ErrorAlert error={menu.error} title="Không tải được menu concept" />}
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {(['style', 'outfit', 'top', 'scene', 'lighting'] as const).map(key => <label key={key} className="grid gap-2 text-sm">
        {{ style: 'Phong cách', outfit: 'Trang phục', top: 'Áo phối cùng', scene: 'Bối cảnh', lighting: 'Ánh sáng' }[key]}
        <select aria-label={{ style: 'Phong cách concept', outfit: 'Trang phục concept', top: 'Áo concept', scene: 'Bối cảnh concept', lighting: 'Ánh sáng concept' }[key]} className="w-full rounded border p-2" value={choices[key]} disabled={!menu.data} onChange={e => change(key, e.target.value)}>
          {menu.data?.[key].map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>)}
    </div>
    {choices.outfit === 'custom' && <label className="grid gap-2 text-sm">Trang phục tùy chỉnh
      <input className="rounded border p-2" maxLength={600} value={choices.custom_outfit} onChange={e => change('custom_outfit', e.target.value)} placeholder="Ví dụ: quần short jeans xanh, áo thun hồng và giày trắng" />
    </label>}
    {choices.scene === 'custom' && <label className="grid gap-2 text-sm">Bối cảnh tùy chỉnh
      <input className="rounded border p-2" maxLength={600} value={choices.custom_scene} onChange={e => change('custom_scene', e.target.value)} placeholder="Ví dụ: hồ bơi trên sân thượng, dù pastel và cây cọ" />
    </label>}
    <label className="grid gap-2 text-sm">Hoạt động tùy chọn
      <input className="rounded border p-2" maxLength={400} value={choices.activity} onChange={e => change('activity', e.target.value)} placeholder="Để trống để tự phối hoạt động theo cảnh" />
    </label>
    <p className="text-xs text-muted-foreground">Lựa chọn được lưu trong trình duyệt này. Trang phục, bối cảnh và prompt thực tế được lưu với từng ảnh trong lịch sử.</p>
  </fieldset>
}
