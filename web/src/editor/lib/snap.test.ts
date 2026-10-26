import { describe, expect, it } from 'vitest'
import { snapPosition } from './snap'

const dims: [number, number, number] = [600, 1200, 2000]
const edge = { grid_mm: 600, align: 'edge' as const }

describe('snapPosition', () => {
  it('edge snaps the footprint corner to the grid', () => {
    expect(snapPosition([1000, 1000], dims, 0, edge, true)).toEqual([900, 1200])
    expect(snapPosition([1000, 1000], dims, 90, edge, true)).toEqual([1200, 900])
    expect(snapPosition([1000, 1000], dims, -90, edge, true)).toEqual([1200, 900])
  })

  it('center snaps the pivot; non-90° rotations fall back to center', () => {
    expect(snapPosition([1000, 1000], dims, 0, { grid_mm: 600, align: 'center' }, true)).toEqual([1200, 1200])
    expect(snapPosition([1000, 1000], dims, 15, edge, true)).toEqual([1200, 1200])
  })

  it('disabled snap returns the point', () => {
    expect(snapPosition([1000, 1001], dims, 0, edge, false)).toEqual([1000, 1001])
  })
})
