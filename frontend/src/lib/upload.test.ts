import { describe, expect, it } from 'vitest'
import { MAX_FILE_BYTES, moveItem, prevalidateFiles, referenceCountWarning } from './upload'

const file = (name: string, type = 'image/png', size = 1000) => {
  const f = new File(['x'], name, { type })
  Object.defineProperty(f, 'size', { value: size })
  return f
}

describe('prevalidateFiles', () => {
  it('accepts supported images', () => {
    const r = prevalidateFiles([file('a.png'), file('b.jpg', 'image/jpeg')], 'reference', 0)
    expect(r.accepted).toHaveLength(2)
    expect(r.errors).toEqual([])
  })

  it('rejects wrong type and oversize', () => {
    const r = prevalidateFiles([file('a.gif', 'image/gif'), file('big.png', 'image/png', MAX_FILE_BYTES + 1)], 'reference', 0)
    expect(r.accepted).toHaveLength(0)
    expect(r.errors).toHaveLength(2)
  })

  it('caps to remaining slots per kind', () => {
    const r = prevalidateFiles([file('a.png'), file('b.png'), file('c.png')], 'reference', 6)
    expect(r.accepted.map((f) => f.name)).toEqual(['a.png', 'b.png'])
    expect(r.errors[0]).toMatch(/Tối đa 8/)
    expect(prevalidateFiles([file('s.png')], 'side_profile', 4).accepted).toHaveLength(0)
  })
})

describe('referenceCountWarning', () => {
  it('warns only for 1–2 photos', () => {
    expect(referenceCountWarning(0)).toBeNull()
    expect(referenceCountWarning(2)).toMatch(/3–8/)
    expect(referenceCountWarning(3)).toBeNull()
  })
})

describe('moveItem', () => {
  it('moves and ignores out-of-range', () => {
    expect(moveItem([1, 2, 3], 0, 2)).toEqual([2, 3, 1])
    expect(moveItem([1, 2, 3], 0, -1)).toEqual([1, 2, 3])
  })
})
