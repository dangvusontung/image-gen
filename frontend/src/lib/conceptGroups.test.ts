import { expect, it } from 'vitest'
import type { ConceptProposal } from '@/api/client'
import { groupConcepts } from './conceptGroups'

it('groups every default once and keeps proposed slot numbers out of default groups', () => {
  const defaults = Array.from({ length: 135 }, (_, i) => ({ id: String(i), slot: i + 1, run: 0 }) as ConceptProposal)
  const groups = groupConcepts(defaults)
  expect(groups.flatMap(g => g.items)).toHaveLength(135)
  expect(groups.find(g => g.name === 'Việt Nam')?.items.map(p => p.slot)).toEqual([85, 86, 87, 88, 89, 90, 91, 92])
  expect(groups.find(g => g.name === 'Private moments')?.items.map(p => p.slot)).toEqual([93, 94, 95, 96, 97, 98, 107, 108])
  expect(groups.find(g => g.name === 'Café vintage & bên cửa sổ')?.items.map(p => p.slot)).toEqual([99, 100, 101])
  expect(groups.find(g => g.name === 'Café sân vườn & cửa sổ xanh')?.items.map(p => p.slot)).toEqual([102, 103, 104])
  expect(groups.find(g => g.name === 'Phòng tắm retro · xanh olive')?.items.map(p => p.slot)).toEqual([105, 106])
  expect(groups.find(g => g.name === 'Ren & thời trang')?.items.map(p => p.slot)).toEqual([109, 110, 111, 112, 113, 114])
  expect(groups.find(g => g.name === 'Camper & du lịch vintage')?.items.map(p => p.slot)).toEqual([117])
  expect(groups.find(g => g.name === 'Phòng khách & sinh hoạt')?.items.map(p => p.slot)).toContain(115)
  expect(groups.find(g => g.name === 'Phòng khách & sinh hoạt')?.items.map(p => p.slot)).toContain(116)
  expect(groups.find(g => g.name === 'Tank top & mini xếp ly')?.items.map(p => p.slot)).toEqual([118, 119, 120, 121])
  expect(groups.find(g => g.name === 'Biển')?.items.map(p => p.slot)).toContain(129)
  expect(groups.find(g => g.name === 'Phòng ngủ & nghỉ ngơi')?.items.map(p => p.slot)).toEqual(expect.arrayContaining([127, 128, 130]))
  expect(groups.find(g => g.name === 'Phòng khách & sinh hoạt')?.items.map(p => p.slot)).toEqual(expect.arrayContaining([131, 132, 133, 134, 135]))
  expect(groups.some(g => g.name === 'Khác')).toBe(false)
  expect(groups.find(g => g.name === 'Bể bơi')?.items.map(p => p.slot)).toEqual([4, ...Array.from({ length: 12 }, (_, i) => i + 29), 122, 123, 124, 125, 126])
  expect(groupConcepts([{ ...defaults[3], run: 1 }])[0].name).toBe('Concept đề xuất')
})


it('groups curated defaults by their stable slot IDs even when earlier slots are retired', () => {
  const slots = [88, 92, 96, 101, 102, 111, 112, 113, 123, 124, 125, 127, 131, 135]
  const concepts = slots.map(slot => ({ id: `default-${slot}`, slot, run: 0 }) as ConceptProposal)
  const groups = groupConcepts(concepts)
  expect(groups.flatMap(g => g.items).map(p => p.slot).sort((a, b) => a - b)).toEqual(slots)
  expect(groups.find(g => g.name === 'Café vintage & bên cửa sổ')?.items.map(p => p.slot)).toEqual([101])
  expect(groups.find(g => g.name === 'Bể bơi')?.items.map(p => p.slot)).toEqual([123, 124, 125])
  expect(groups.some(g => g.name === 'Khác')).toBe(false)
})
