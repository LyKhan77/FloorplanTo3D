import { describe, expect, it } from 'vitest'
import { walkStep } from './walk'

const free = () => false
const round = (p: [number, number]) => p.map((v) => Math.round(v) + 0)

describe('walkStep', () => {
  it('walks 1.4 m/s, runs 3 m/s, stops when blocked', () => {
    expect(round(walkStep([0, 0], 0, { f: 1, r: 0 }, 1, false, free))).toEqual([0, 1400])
    expect(round(walkStep([0, 0], 0, { f: 1, r: 0 }, 1, true, free))).toEqual([0, 3000])
    expect(round(walkStep([0, 0], 0, { f: 0, r: 1 }, 1, false, free))).toEqual([1400, 0])
    expect(round(walkStep([0, 0], Math.PI / 2, { f: 1, r: 0 }, 1, false, free))).toEqual([-1400, 0])
    expect(round(walkStep([500, 500], 0, { f: 1, r: 0 }, 1, false, () => true))).toEqual([500, 500])
    const diag = walkStep([0, 0], 0, { f: 1, r: 1 }, 1, false, free)
    expect(Math.hypot(...diag)).toBeCloseTo(1400)
    expect(walkStep([7, 7], 0, { f: 0, r: 0 }, 1, false, free)).toEqual([7, 7])
  })
})
