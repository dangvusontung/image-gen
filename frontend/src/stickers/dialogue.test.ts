import { describe, expect, it } from 'vitest'
import { freshJob, previewUrl, type Pack, type StickerItem } from './api'
import { suggestReaction } from './DialogueEditor'

const item: StickerItem = { id: 'hello', caption: 'Hi!', expression: 'Waving hello', emoji: '👋' }
const pack = { id: 'pack', style: 'chibi', approved_concept: { id: 'concept' }, jobs: { hello: { id: 'job', status: 'succeeded', meta: { concept_job_id: 'concept', artwork_version: 2, style: 'chibi', sticker_item: item } } } } as unknown as Pack

describe('separate artwork and dialogue', () => {
  it('reuses artwork for text, bubble, placement, font size and emoji edits', () => {
    expect(freshJob(pack, { ...item, caption: 'Ủa, thiệt luôn?', text_style: 'speech', text_x: .4, text_y: .2, text_size: 32, emoji: '😮' })).toBe(true)
    expect(freshJob(pack, { ...item, expression: 'Facepalm' })).toBe(false)
    expect(freshJob({ ...pack, style: 'clay' }, item)).toBe(false)
    expect(freshJob({ ...pack, approved_concept: null }, item)).toBe(false)
    expect(freshJob({ ...pack, approved_concept: { ...pack.approved_concept!, id: 'different-look' } }, item)).toBe(false)
  })
  it('changes the preview URL after text edits without changing the artwork job', () => {
    expect(previewUrl(pack, item)).not.toBe(previewUrl(pack, { ...item, caption: 'Different text' }))
    expect(previewUrl(pack, { ...item, caption: 'Ủa?' })).toContain('job_id=job')
  })
  it('requires regeneration of legacy images that may contain model-generated text', () => {
    const legacy = { ...pack, jobs: { hello: { ...pack.jobs.hello, meta: { style: 'chibi', sticker_item: item } } } }
    expect(freshJob(legacy, item)).toBe(false)
  })
  it('suggests editable local poses for English and Vietnamese dialogue', () => {
    expect(suggestReaction('Hết cứu!')).toMatch(/Facepalming/)
    expect(suggestReaction('Ủa, thiệt luôn?')).toMatch(/Confused/)
    expect(suggestReaction('Thank you')).toMatch(/Grateful/)
    expect(suggestReaction('A brand new phrase')).toMatch(/Speaking expressively/)
  })
})
