import { expect, it } from 'vitest'
import type { ConceptProposal } from '@/api/client'
import { groupConcepts } from './conceptGroups'

it('groups every default once and keeps proposed slot numbers out of default groups', () => {
  const defaults = Array.from({ length: 72 }, (_, i) => ({ id: String(i), slot: i + 1, run: 0 }) as ConceptProposal)
  const groups = groupConcepts(defaults)
  expect(groups.flatMap(g => g.items)).toHaveLength(72)
  expect(groups.some(g => g.name === 'Khác')).toBe(false)
  expect(groups.find(g => g.name === 'Bể bơi')?.items.map(p => p.slot)).toEqual([4, ...Array.from({ length: 12 }, (_, i) => i + 29)])
  expect(groupConcepts([{ ...defaults[3], run: 1 }])[0].name).toBe('Concept đề xuất')
})
