import { describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { ReviewTask } from '../../api/types'
import type { Spec, Wall } from '../../types/spec'
import { applyOps } from '../ops/reducer'
import { closeGapOps, doorAtOps, guideLineOps } from './tools'

const gt = gtJson as unknown as Spec
const wall = (id: string, a: [number, number], b: [number, number]) =>
  ({ id, a, b, thickness: 120, kind: 'interior', provenance: { source: 'cv', confidence: 0.9 } }) as unknown as Wall

function withGap(firstEnd: 'a' | 'b' = 'b'): { spec: Spec; task: ReviewTask } {
  const spec = structuredClone(gt)
  const w1 = firstEnd === 'b' ? wall('W900', [50000, 0], [52000, 0]) : wall('W900', [52000, 0], [50000, 0])
  spec.walls = [...spec.walls!, w1, wall('W901', [52900, 0], [55000, 0])]
  const task: ReviewTask = { id: 'gap:W900,W901', kind: 'gap', message: 'Celah 0.9 m', at: [52450, 0], element_ids: ['W900', 'W901'],
    fix: { a: [52000, 0], b: [52900, 0], thickness: 120, kind: 'interior', ends: [{ wall: 'W900', end: firstEnd }, { wall: 'W901', end: 'a' }] } }
  return { spec, task }
}

describe('review tools', () => {
  it('closeGapOps extends the wall with the dangling b end and puts the door on it', () => {
    const { spec, task } = withGap('b')
    const { ops } = closeGapOps(task, true, spec)
    const out = applyOps(spec, ops)
    expect(out.failed).toEqual([])
    const w = out.spec.walls!.find((x) => x.id === 'W900')!
    expect(w.b).toEqual([52900, 0])
    const door = out.spec.openings!.find((o) => o.wall_id === 'W900')!
    expect(door).toMatchObject({ category: 'door', offset: 2000, width: 850 })
  })

  it('without the door only the wall is extended', () => {
    const { spec, task } = withGap('b')
    expect(closeGapOps(task, false, spec).ops).toEqual([{ op: 'move_wall', id: 'W900', b: [52900, 0] }])
  })

  it('when no wall has its b end at the gap, a new wall closes it and the door waits for a save', () => {
    const { spec, task } = withGap('a')
    const r = closeGapOps(task, true, spec)
    expect(r.ops).toEqual([{ op: 'add_wall', a: [52000, 0], b: [52900, 0], thickness: 120, kind: 'interior' }])
    expect(r.doorSkipped).toBe('needs-save')
  })

  it('a gap too narrow for a door is closed without one', () => {
    const { spec, task } = withGap('b')
    task.fix.b = [52600, 0]  // 600 mm: 550 mm of door after the 50 mm margin
    const r = closeGapOps(task, true, spec)
    expect(r.ops).toEqual([{ op: 'move_wall', id: 'W900', b: [52600, 0] }])
    expect(r.doorSkipped).toBe('too-narrow')
  })

  it('the door fits the extended wall with the 50 mm end margin (V008)', () => {
    const { spec, task } = withGap('b')
    task.fix.b = [52900, 40]  // a slightly askew target: the new length is not len + gap
    const out = applyOps(spec, closeGapOps(task, true, spec).ops)
    const w = out.spec.walls!.find((x) => x.id === 'W900')!
    const door = out.spec.openings!.find((o) => o.wall_id === 'W900')!
    expect(door.offset + door.width).toBeLessThanOrEqual(Math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1]) - 50)
  })

  it('guideLineOps uses the snapped thickness', () => {
    expect(guideLineOps({ a: [0, 0], b: [3000, 0], thickness: 150 })).toEqual(
      [{ op: 'add_wall', a: [0, 0], b: [3000, 0], thickness: 150, kind: 'partition' }])
  })
})

describe('doorAtOps', () => {
  const spec = () => {
    const s = structuredClone(gt)
    s.walls = [...s.walls!, wall('W900', [50000, 0], [54000, 0]), wall('W901', [60000, 0], [60800, 0]), wall('W902', [70000, 0], [70500, 0])]
    return s
  }
  it('puts a 900 mm door centred on the click, on the wall under it', () => {
    const op = doorAtOps(spec(), [52000, 80])
    expect(op).toEqual({ op: 'add_opening', wall_id: 'W900', category: 'door', offset: 1550, width: 900,
      door_type: 'single_swing', hinge: 'start', swing: 'left' })
    expect(applyOps(spec(), [op!]).failed).toEqual([])
  })
  it('keeps 50 mm from either wall end', () => {
    expect(doorAtOps(spec(), [50100, 0])).toMatchObject({ offset: 50 })
    expect(doorAtOps(spec(), [53990, 0])).toMatchObject({ offset: 4000 - 900 - 50 })
  })
  it('narrows the door on a short wall, and refuses walls too short for 600 mm', () => {
    expect(doorAtOps(spec(), [60400, 0])).toMatchObject({ wall_id: 'W901', offset: 50, width: 700 })
    expect(doorAtOps(spec(), [70250, 0])).toBeNull()
  })
  it('refuses a click away from every wall', () => {
    expect(doorAtOps(spec(), [52000, 1000])).toBeNull()
  })
})

