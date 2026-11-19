import { expect, it } from 'vitest'
import type { ConceptProposal } from '@/api/client'
import { isArchivedConcept, matchesConceptArchive } from './conceptArchive'

it('distinguishes archived catalog entries from custom concepts and missing metadata', () => {
  const archived = { run: 0, display_number: null } as ConceptProposal
  const custom = { run: 1, display_number: null } as ConceptProposal
  const legacy = { run: 0 } as ConceptProposal
  expect(isArchivedConcept(archived)).toBe(true)
  expect(isArchivedConcept(custom)).toBe(false)
  expect(isArchivedConcept(legacy)).toBe(false)
  expect(matchesConceptArchive(archived, 'active')).toBe(false)
  expect(matchesConceptArchive(archived, 'archived')).toBe(true)
  expect(matchesConceptArchive(custom, 'all')).toBe(true)
})
