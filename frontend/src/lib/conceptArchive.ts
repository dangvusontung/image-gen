import type { ConceptProposal } from '@/api/client'

export type ConceptArchiveFilter = 'active' | 'archived' | 'all'

export const isArchivedConcept = (row: ConceptProposal) => row.archived ?? (row.run === 0 && row.display_number === null)
export const matchesConceptArchive = (row: ConceptProposal, filter: ConceptArchiveFilter) => filter === 'all' || isArchivedConcept(row) === (filter === 'archived')
