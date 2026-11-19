import { expect, it } from 'vitest'
import type { ConceptProposal } from '@/api/client'
import { groupConcepts } from './conceptGroups'

const proposal = (slot: number, run = 0) => ({ id: `${run}-${slot}`, slot, run }) as ConceptProposal

it('groups every catalog slot exactly once without a fallback', () => {
  const defaults = Array.from({ length: 190 }, (_, i) => proposal(i + 1))
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

it('uses backend taxonomy to group similar poses across scenes without losing variants', async () => {
  const { conceptDisplayNumbers } = await import('./conceptGroups')
  const concepts = [
    { ...proposal(183), group: 'Phòng khách & sinh hoạt', family: 'Ôm gối & ôm chân', display_number: 12 },
    { ...proposal(170), group: 'Studio & chân dung', family: 'Ôm gối & ôm chân', display_number: 131 },
    { ...proposal(54), group: 'Bếp & bên cửa sổ', family: 'Cầm cốc & đồ uống', display_number: 70 },
  ]
  const families = groupConcepts(concepts, 'family')
  expect(families.find(group => group.name === 'Ôm gối & ôm chân')?.items.map(row => row.slot)).toEqual([183, 170])
  expect(groupConcepts(concepts).find(group => group.name === 'Bếp & bên cửa sổ')?.items[0].slot).toBe(54)
  expect(conceptDisplayNumbers(concepts.filter(row => row.slot === 170)).get(170)).toBe(131)
})


it('keeps beach concepts in one collection across different scenes and poses', () => {
  const rows = [
    { ...proposal(164), group: 'Biển', family: 'Đứng', collection_id: 'beach', collection_name: 'Beach · Biển', display_number: 30 },
    { ...proposal(92), group: 'Việt Nam', family: 'Đi bộ', collection_id: 'beach', collection_name: 'Beach · Biển', display_number: 20 },
    { ...proposal(210), group: 'Biển', family: 'Đứng', collection_id: 'beach', collection_name: 'Beach · Biển', display_number: 35 },
    { ...proposal(1), group: 'Phòng khách & sinh hoạt', display_number: 1 },
  ]
  const groups = groupConcepts(rows, 'collection')
  expect(groups.find(group => group.name === 'Beach · Biển')?.items.map(row => row.slot)).toEqual([92, 164, 210])
  expect(groups.flatMap(group => group.items)).toHaveLength(4)
  expect(groups.some(group => group.name === 'Phòng khách & sinh hoạt')).toBe(true)
})
