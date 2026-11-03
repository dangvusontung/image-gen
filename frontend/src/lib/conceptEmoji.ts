export const CONCEPT_EMOJIS = ['⭐', '❤️', '🔥', '🌿', '🌊', '🏠', '☕', '🌙', '📸', '✅']
export const CONCEPT_EMOJI_STORAGE = 'concept-emoji-marks:v1'
export type EmojiMarks = Record<string, string>

export function conceptMarkKey(projectId: string, proposal: { run: number; slot: number }) {
  return proposal.run === 0 ? `default:${proposal.slot}` : `project:${projectId}:run:${proposal.run}:slot:${proposal.slot}`
}

export function readEmojiMarks(): EmojiMarks {
  try {
    const saved = JSON.parse(localStorage.getItem(CONCEPT_EMOJI_STORAGE) || '{}')
    if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return {}
    return Object.fromEntries(Object.entries(saved).filter((entry): entry is [string, string] => typeof entry[1] === 'string' && CONCEPT_EMOJIS.includes(entry[1])))
  } catch { return {} }
}
