import type { ConceptProposal } from '@/api/client'

const GROUPS = [
  { name: 'Glamour & ánh đèn', slots: [61, 62, 63, 64, 65, 66] },
  { name: 'Biển', slots: [49, 50, 51, 52] },
  { name: 'Sinh hoạt ở nhà', slots: [53, 54, 55, 56] },
  { name: 'Chân dung cận', slots: [57, 58, 59, 60] },
  { name: 'Bể bơi', slots: [4, ...Array.from({ length: 12 }, (_, i) => i + 29)] },
  { name: 'Phòng ngủ & nghỉ ngơi', slots: [2, 5, 11, 15, 16, 18, 19, 20, 24, 25, 41, 42, 43, 44] },
  { name: 'Phòng khách & sinh hoạt', slots: [1, 9, 10, 17, 21, 28] },
  { name: 'Bếp & bên cửa sổ', slots: [12, 13, 14, 27] },
  { name: 'Ngoài trời & ban công', slots: [3, 6, 8, 26] },
  { name: 'Công việc & bàn trang điểm', slots: [7, 23] },
  { name: 'Phòng tắm', slots: [22, 45, 46, 47, 48] },
]

export function groupConcepts(concepts: ConceptProposal[]) {
  const grouped = new Map<string, ConceptProposal[]>()
  for (const concept of concepts) {
    const name = concept.run === 0
      ? GROUPS.find(group => group.slots.includes(concept.slot))?.name ?? 'Khác'
      : 'Concept đề xuất'
    const items = grouped.get(name) ?? []
    items.push(concept)
    grouped.set(name, items)
  }
  return Array.from(grouped, ([name, items]) => ({ name, items }))
}
