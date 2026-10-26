import { describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { SetStair } from '../../types/ops'
import type { Spec } from '../../types/spec'
import { applyOps } from '../ops/reducer'
import { geometryDiff } from './geometryDiff'

const gt = gtJson as unknown as Spec

describe('geometryDiff', () => {
  it('geometryDiff classifies added, moved and deleted', () => {
    const w1 = gt.walls![0]
    const s1 = gt.stairs![0]
    const view = applyOps(gt, [
      { op: 'move_wall', id: w1.id, a: [w1.a[0] + 100, w1.a[1]] },
      { op: 'add_wall', a: [0, 0], b: [3000, 0], thickness: 150, kind: 'partition' },
      { op: 'delete_opening', id: 'D1', reason: 'x' },
      { op: 'set_stair', id: s1.id, flights: s1.flights.map((f) => ({ ...f, start: f.end, end: f.start })) as SetStair['flights'] },
      { op: 'set_wall_height', id: 'W2', height: 4500 },
    ]).spec
    const d = geometryDiff(gt, view)
    expect(d.walls.map((x) => [x.id, x.state])).toEqual([['W1', 'moved'], ['W78', 'added']])
    expect(d.openings.map((x) => [x.id, x.state])).toEqual([['D1', 'deleted']])
    expect(d.stairs.map((x) => [x.id, x.state])).toEqual([[s1.id, 'moved']])
    expect(geometryDiff(gt, gt)).toEqual({ walls: [], openings: [], stairs: [] })
  })
})
