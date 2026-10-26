import { describe, expect, it } from 'vitest'
import { summarizeDiff } from './diff'

describe('summarizeDiff', () => {
  it('summarizes changed types only', () => {
    expect(summarizeDiff({
      walls: { added: ['W6'], removed: [], changed: ['W1'] },
      openings: { added: [], removed: ['D2'], changed: [] },
      rooms: { added: [], removed: [], changed: [] },
    })).toEqual(['Dinding: +1 −0 ~1', 'Bukaan: +0 −1 ~0'])
  })
})
