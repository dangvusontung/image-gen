import { describe, expect, it } from 'vitest'
import type { Concept } from '@/api/client'
import { conceptProgress, matchesProgress, progressLabel } from './conceptProgress'

const row = (run: number, revision: number, status: string, ids: string[] = [], key = 'default:155') => ({
  id: `${run}-${revision}`, slot: 155, run, revision, bookmark_key: key,
  job: { status, output_asset_ids: ids },
}) as Concept

describe('concept progress within one project', () => {
  it('keeps successes across batches while a new version is running', () => {
    const state = conceptProgress([row(1, 1, 'succeeded', ['a']), row(2, 1, 'succeeded', ['b']), row(2, 2, 'running')]).get('default:155')!
    expect(state.imageIds).toEqual(['a', 'b'])
    expect(matchesProgress(state, 'created')).toBe(true)
    expect(matchesProgress(state, 'active')).toBe(true)
    expect(matchesProgress(state, 'uncreated')).toBe(false)
    expect(progressLabel(state)).toContain('Đang tạo')
    expect(state.rows[0].revision).toBe(2)
  })
  it('does not count errors, cancelled jobs or missing outputs as images', () => {
    const failed = conceptProgress([row(1, 1, 'failed'), row(1, 2, 'cancelled')]).get('default:155')!
    expect(failed.imageIds).toEqual([])
    expect(matchesProgress(failed, 'failed')).toBe(true)
    expect(matchesProgress(failed, 'created')).toBe(false)
    expect(matchesProgress(undefined, 'uncreated')).toBe(true)
    expect(progressLabel(undefined)).toBe('Chưa tạo')
  })
  it('separates project histories and unrelated concepts with the same slot', () => {
    const first = conceptProgress([row(1, 1, 'succeeded', ['a'])])
    const second = conceptProgress([row(1, 1, 'succeeded', ['b'], 'project:other:run:1:slot:155')])
    expect(matchesProgress(first.get('default:155'), 'created')).toBe(true)
    expect(matchesProgress(second.get('default:155'), 'uncreated')).toBe(true)
  })
})
