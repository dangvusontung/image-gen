import { expect, it } from 'vitest'
import type { ConceptProposal } from '@/api/client'
import { groupConcepts } from './conceptGroups'

it('groups every default once and keeps proposed slot numbers out of default groups', () => {
  const defaults = Array.from({ length: 108 }, (_, i) => ({ id: String(i), slot: i + 1, run: 0 }) as ConceptProposal)
  const groups = groupConcepts(defaults)
  expect(groups.flatMap(g => g.items)).toHaveLength(108)
  expect(groups.find(g => g.name === 'Việt Nam')?.items.map(p => p.slot)).toEqual([85, 86, 87, 88, 89, 90, 91, 92])
  expect(groups.find(g => g.name === 'Private moments')?.items.map(p => p.slot)).toEqual([93, 94, 95, 96, 97, 98, 107, 108])
  expect(groups.find(g => g.name === 'Café vintage & bên cửa sổ')?.items.map(p => p.slot)).toEqual([99, 100, 101])
  expect(groups.find(g => g.name === 'Café sân vườn & cửa sổ xanh')?.items.map(p => p.slot)).toEqual([102, 103, 104])
  expect(groups.find(g => g.name === 'Phòng tắm retro · xanh olive')?.items.map(p => p.slot)).toEqual([105, 106])
  expect(groups.some(g => g.name === 'Khác')).toBe(false)
  expect(groups.find(g => g.name === 'Bể bơi')?.items.map(p => p.slot)).toEqual([4, ...Array.from({ length: 12 }, (_, i) => i + 29)])
  expect(groupConcepts([{ ...defaults[3], run: 1 }])[0].name).toBe('Concept đề xuất')
})
