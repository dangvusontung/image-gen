import { beforeEach, expect, it } from 'vitest'
import { conceptMarkKey, CONCEPT_EMOJI_STORAGE, readEmojiMarks } from './conceptEmoji'

beforeEach(() => localStorage.clear())
it('shares default marks across projects and isolates proposed rounds and projects', () => {
  expect(conceptMarkKey('a', { run: 0, slot: 131 })).toBe(conceptMarkKey('b', { run: 0, slot: 131 }))
  expect(conceptMarkKey('a', { run: 1, slot: 1 })).not.toBe(conceptMarkKey('b', { run: 1, slot: 1 }))
  expect(conceptMarkKey('a', { run: 1, slot: 1 })).not.toBe(conceptMarkKey('a', { run: 2, slot: 1 }))
})
it('restores supported marks and tolerates corrupted storage', () => {
  localStorage.setItem(CONCEPT_EMOJI_STORAGE, JSON.stringify({ 'default:131': '⭐', invalid: 42 }))
  expect(readEmojiMarks()).toEqual({ 'default:131': '⭐' })
  localStorage.setItem(CONCEPT_EMOJI_STORAGE, 'broken')
  expect(readEmojiMarks()).toEqual({})
})
