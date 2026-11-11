import { expect, it } from 'vitest'
import type { ConceptProposal } from '@/api/client'
import { groupConcepts } from './conceptGroups'

const proposal = (slot: number, run = 0) => ({ id: `${run}-${slot}`, slot, run }) as ConceptProposal

it('groups every catalog slot exactly once without a fallback', () => {
  const defaults = Array.from({ length: 158 }, (_, i) => proposal(i + 1))
  const groups = groupConcepts(defaults)
  expect(groups).toHaveLength(13)
  expect(groups.flatMap(g => g.items).map(p => p.slot).sort((a, b) => a - b)).toEqual(defaults.map(p => p.slot))
  expect(groups.some(g => g.name === 'Khác')).toBe(false)
})

it('consolidates related scenes and keeps filtered sections in stable order', () => {
  const groups = groupConcepts([123, 127, 131, 101, 102, 136, 105, 96, 144, 61, 67, 111, 118].map(slot => proposal(slot)))
  const slotsIn = (name: string) => groups.find(g => g.name === name)?.items.map(p => p.slot)
  expect(slotsIn('Café')).toEqual([101, 102, 136])
  expect(slotsIn('Phòng tắm')).toEqual([105, 96, 144])
  expect(slotsIn('Thời trang & ánh đèn')).toEqual([61, 67, 111, 118])
  expect(groups[0].name).toBe('Phòng khách & sinh hoạt')
})

it('keeps proposed and unknown slots separate from default concepts', () => {
  const concepts = [proposal(999), proposal(123, 1), proposal(123)]
  const groups = groupConcepts(concepts)
  expect(groups.map(g => g.name)).toEqual(['Bể bơi', 'Khác', 'Concept đề xuất'])
  expect(groups[0].items).toEqual([concepts[2]])
  expect(groups[2].items).toEqual([concepts[1]])
})

it('numbers the grouped picker continuously while preserving stable slot IDs', async () => {
  const { conceptDisplayNumbers } = await import('./conceptGroups')
  const concepts = [131, 127, 12, 105, 101, 123, 50, 3, 61, 57, 140].map(slot => proposal(slot))
  const numbers = conceptDisplayNumbers(concepts)
  expect([...numbers.values()]).toEqual(Array.from({ length: concepts.length }, (_, i) => i + 1))
  expect(numbers.get(131)).toBe(1)
  expect(numbers.get(127)).toBe(2)
  expect(numbers.get(140)).toBe(11)
  expect(concepts[0].slot).toBe(131)
  // A filter uses the full catalog map, so a visible concept keeps its number.
  expect(concepts.filter(p => p.slot === 140).map(p => numbers.get(p.slot))).toEqual([11])
})
