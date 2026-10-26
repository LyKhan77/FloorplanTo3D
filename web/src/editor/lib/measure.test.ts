import { describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { distance, formatM, formatM2, gridIntersections, lockAxis, nearestSnap, shoelaceM2 } from './measure'

const gt = gtJson as unknown as Spec

describe('measure', () => {
  it('distance gives the 3-4-5 triangle and its deltas', () => {
    expect(distance([0, 0, 0], [3000, 4000, 0])).toEqual({ d: 5000, dx: 3000, dy: 4000, dz: 0 })
  })

  it('lockAxis keeps the largest delta only', () => {
    expect(lockAxis([0, 0, 0], [100, 900, 30])).toEqual([0, 900, 0])
    expect(lockAxis([10, 10, 0], [10, 20, 3000])).toEqual([10, 10, 3000])
  })

  it('shoelaceM2 of R. MEETING matches its area_m2', () => {
    const room = gt.rooms!.find((r) => r.name === 'R. MEETING')!
    expect(Math.abs(shoelaceM2(room.polygon) - room.area_m2!)).toBeLessThanOrEqual(0.01)
  })

  it('formats meters with 3 decimals and m² with 2', () => {
    expect(formatM(12400)).toBe('12.400 m')
    expect(formatM(5)).toBe('0.005 m')
    expect(formatM2(57.6234)).toBe('57.62 m²')
  })

  it('nearestSnap picks the closest candidate within 10 px', () => {
    const c = [{ screen: [100, 100] as [number, number], id: 'a' }, { screen: [105, 100] as [number, number], id: 'b' }]
    expect(nearestSnap([104, 100], c)?.id).toBe('b')
    expect(nearestSnap([120, 100], c)).toBeNull()
    expect(nearestSnap([114, 100], c)?.id).toBe('b')
  })

  it('gridIntersections crosses every vertical with every horizontal axis', () => {
    const axes = gt.grid!.axes!
    const v = axes.filter((a) => a.orientation === 'vertical'), h = axes.filter((a) => a.orientation === 'horizontal')
    const pts = gridIntersections(gt)
    expect(pts).toHaveLength(v.length * h.length)
    expect(pts).toContainEqual([v[1].offset, h[0].offset])
  })
})
