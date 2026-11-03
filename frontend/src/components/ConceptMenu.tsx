import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { request } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'

export interface ConceptChoices {
  footwear?: string; custom_footwear?: string
  glasses?: boolean
  style: string; outfit: string; top: string; scene: string; lighting: string
  custom_outfit: string; custom_scene: string; activity: string
}
// Keep each concept's own clothing unless the user explicitly selects an override.
export const CONCEPT_DEFAULTS: ConceptChoices = { footwear: 'auto', custom_footwear: '', glasses: false, style: 'auto', outfit: 'auto', top: 'auto', scene: 'auto', lighting: 'auto', custom_outfit: '', custom_scene: '', activity: '' }

export const overridesConcept = (c: ConceptChoices) =>
  (c.footwear !== undefined && c.footwear !== 'auto') || Boolean(c.glasses) || c.style !== 'auto' || c.outfit !== 'auto' || c.top !== 'auto' || c.scene !== 'auto' ||
  c.lighting !== 'auto' || Boolean(c.activity.trim())

export function useConceptChoices(projectId: string) {
  const key = `concept-choices:${projectId}`
  const [choices, setChoices] = useState<ConceptChoices>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(key) || '{}')
      if (!localStorage.getItem(`${key}:outfit-default-v2`) && saved.outfit === 'bikini') saved.outfit = 'auto'
      return { ...CONCEPT_DEFAULTS, ...saved }
    } catch { return CONCEPT_DEFAULTS }
  })
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(choices)); localStorage.setItem(`${key}:outfit-default-v2`, '1') } catch { /* Browser storage may be unavailable. */ } }, [key, choices])
  return [choices, setChoices] as const
}

export function ConceptMenu({ projectId, choices, onChange }: { projectId: string; choices: ConceptChoices; onChange: (choices: ConceptChoices) => void }) {
  const menu = useQuery({ queryKey: ['concept-options', projectId], queryFn: () => request<Record<string, [string, string][]>>(`/projects/${projectId}/concept-options`) })
  const change = (key: keyof ConceptChoices, value: string) => onChange({ ...choices, [key]: value })
  return <fieldset className="space-y-4 rounded-xl border p-4">
    <legend className="px-2 font-semibold">Chọn trang phục và bối cảnh</legend>
    <p className="text-sm text-muted-foreground">Áp dụng cho ảnh tạo mới và nút tạo lại ô. Có thể tạo nhiều đợt với lựa chọn khác nhau; mỗi ô vẫn có biểu cảm và góc máy riêng.</p>
    {overridesConcept(choices) && <div className="flex flex-wrap items-center gap-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm">
      <span role="status" className="text-amber-800">
        Đang ghi đè mô tả của <strong>tất cả</strong> concept bằng lựa chọn bên dưới.
      </span>
      <button type="button" className="rounded border bg-background px-3 py-1" onClick={() => onChange({ ...CONCEPT_DEFAULTS, outfit: 'auto' })}>
        Dùng mô tả gốc của từng concept
      </button>
    </div>}
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(choices.glasses)} onChange={e => onChange({ ...choices, glasses: e.target.checked })} />+ Kính (tùy chọn)</label>
    {menu.error && <ErrorAlert error={menu.error} title="Không tải được menu concept" />}
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {(['style', 'outfit', 'footwear', 'top', 'scene', 'lighting'] as const).map(key => <label key={key} className="grid gap-2 text-sm">
        {{ style: 'Phong cách', outfit: 'Quần áo', footwear: 'Giày', top: 'Áo phối cùng', scene: 'Bối cảnh', lighting: 'Ánh sáng' }[key]}
        <select aria-label={{ style: 'Phong cách concept', outfit: 'Trang phục concept', footwear: 'Giày concept', top: 'Áo concept', scene: 'Bối cảnh concept', lighting: 'Ánh sáng concept' }[key]} className="w-full rounded border p-2" value={choices[key]} disabled={!menu.data} onChange={e => change(key, e.target.value)}>
          {menu.data?.[key].map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>)}
    </div>
    {choices.footwear === 'custom' && <label className="grid gap-2 text-sm">Giày tùy chỉnh<input className="rounded border p-2" maxLength={400} value={choices.custom_footwear ?? ''} onChange={e => change('custom_footwear', e.target.value)} placeholder="Ví dụ: slingback đỏ mũi nhọn, gót nhọn thấp…" /></label>}
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


export function OutfitSwitcher({ choices, onChange }: { choices: ConceptChoices; onChange: (next: ConceptChoices) => void }) {
  const outfits = [['black_strapless_mini', 'Váy mini đen cúp ngực'], ['auto', 'Trang phục riêng của từng concept (mặc định)'], ['tank_pleated_classic', 'Tank trắng + mini xếp ly xám'], ['tank_pleated_minimal', 'Tank đen + mini xếp ly kem'], ['tank_pleated_sport', 'Tank xanh pastel + mini xếp ly trắng'], ['tank_pleated_vintage', 'Tank đỏ rượu + mini xếp ly taupe'], ['white_strapless_mini', 'Váy mini satin trắng cúp ngực'], ['black_white_lounge', 'Crop tank + short đen viền trắng'], ['bikini', 'Bikini'], ['satin_dress', 'Váy satin'], ['satin_pyjamas', 'Bộ ngủ satin'], ['shirt_shorts', 'Sơ mi + quần short'], ['bodysuit_trousers', 'Bodysuit + quần dài'], ['offshoulder_skirt', 'Áo trễ vai + chân váy']]
  return <div className="flex flex-wrap items-end gap-4 rounded-xl border p-4">
    <label className="grid gap-2 text-sm font-medium">Trang phục
      <select aria-label="Đổi trang phục concept" className="rounded border bg-background p-2" value={choices.outfit} onChange={e => onChange({ ...choices, outfit: e.target.value, top: 'auto' })}>
        {outfits.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        {!outfits.some(([value]) => value === choices.outfit) && <option value={choices.outfit}>Trang phục tùy chọn từ menu nâng cao</option>}
      </select>
    </label>
    <label className="grid gap-2 text-sm font-medium">Giày
      <select aria-label="Đổi giày concept" className="rounded border bg-background p-2" value={choices.footwear ?? 'auto'} onChange={e => onChange({ ...choices, footwear: e.target.value })}>
        <option value="auto">Giày riêng của từng concept</option>
        <option value="white_slingback">Slingback trắng · mũi nhọn, quai đôi, gót đen</option>
        <option value="black_pumps">Pumps đen gót nhọn</option>
        <option value="sneakers">Sneakers trắng</option>
        <option value="barefoot">Chân trần · không tất</option>
        {choices.footwear === 'custom' && <option value="custom">Giày tùy chỉnh từ menu nâng cao</option>}
      </select>
    </label>
    <label className="flex items-center gap-2 py-2 text-sm"><input type="checkbox" checked={Boolean(choices.glasses)} onChange={e => onChange({ ...choices, glasses: e.target.checked })} />+ Kính</label>
    <p className="text-xs text-muted-foreground">Áp dụng cho concept bạn chọn khi tạo ảnh hoặc tạo lại. Mỗi concept vẫn giữ bối cảnh, tư thế và màu phối riêng.</p>
  </div>
}
