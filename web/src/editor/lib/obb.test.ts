import { describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { applyOps } from '../ops/reducer'
import { collisions, footprint, overlaps } from './obb'

const gt = gtJson as unknown as Spec
const rack = (x: number, y: number, rotation = 0) => ({ position: [x, y, 0] as [number, number, number], rotation,
  dims: [600, 1200, 2000] as [number, number, number] })

describe('obb', () => {
  it('touching edges do not collide, 10 mm overlap does', () => {
    expect(overlaps(footprint(rack(0, 0)), footprint(rack(600, 0)))).toBe(false)
    expect(overlaps(footprint(rack(0, 0)), footprint(rack(590, 0)))).toBe(true)
  })

  it('footprint is CCW and rotates about the pivot', () => {
    const f = footprint(rack(0, 0, 90))
    expect(f.map(([x, y]) => [Math.round(x), Math.round(y)])).toEqual([[600, -300], [600, 300], [-600, 300], [-600, -300]])
  })

  it('a 45° rotation is caught by SAT where AABB would be wrong', () => {
    const diamond = footprint({ position: [0, 0, 0], rotation: 45, dims: [1000, 1000, 1000] })
    const box = (x0: number) => footprint({ position: [x0 + 500, x0 + 500, 0], rotation: 0, dims: [1000, 1000, 1000] })
    expect(overlaps(diamond, box(600))).toBe(false)
    expect(overlaps(diamond, box(300))).toBe(true)
  })

  it('collisions reports object vs wall, object vs object and object vs column', () => {
    const w1 = gt.walls![0]
    const c1 = gt.columns![0]
    const add = (x: number, y: number) => ({ op: 'add_object' as const, template_id: 'r', template_version: '1',
      position: [x, y, 0] as [number, number, number], rotation: 0, dims: [600, 1200, 2000] as [number, number, number] })
    const spec = applyOps(gt, [add(1000, w1.a[1]), add(8000, 8000), add(8300, 8000), add(c1.center[0], c1.center[1])]).spec
    const hits = collisions(spec)
    expect(hits).toContainEqual({ a: 'O1', b: 'W1' })
    expect(hits).toContainEqual({ a: 'O2', b: 'O3' })
    expect(hits).toContainEqual({ a: 'O4', b: c1.id })
    expect(hits.some((h) => h.a === 'O2' && h.b.startsWith('W'))).toBe(false)
  })
})
