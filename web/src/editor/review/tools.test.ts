import { describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { ReviewTask } from '../../api/types'
import type { Spec, Wall } from '../../types/spec'
import { applyOps, type EditorOp } from '../ops/reducer'
import { closeGapOps, doorOps, guideLineOps } from './tools'

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

  it('when no wall has its b end at the gap, a new wall closes it and carries the door', () => {
    const { spec, task } = withGap('a')
    const r = closeGapOps(task, true, spec)
    expect(r.ops).toEqual([{ op: 'add_wall', a: [52000, 0], b: [52900, 0], thickness: 120, kind: 'interior',
      openings: [{ category: 'door', offset: 50, width: 800, door_type: 'single_swing', hinge: 'start', swing: 'left' }] }])
    expect(r.doorSkipped).toBeNull()
    const out = applyOps(spec, r.ops)
    expect(out.failed).toEqual([])
    expect(out.spec.openings!.at(-1)).toMatchObject({ wall_id: out.spec.walls!.at(-1)!.id, offset: 50, width: 800 })
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

describe('doorOps', () => {
  const door = { id: 'D900', wall_id: 'W900', category: 'door', offset: 3000, width: 800, sill: 0 }
  const spec = () => {
    const s = structuredClone(gt)
    s.walls = [...s.walls!, wall('W900', [50000, 0], [54000, 0]), wall('W903', [54900, 0], [58000, 0]),
      wall('W901', [60000, 0], [60800, 0]), wall('W902', [70000, 0], [70500, 0])]
    s.openings = [...s.openings!, door as never]
    return s
  }
  const DOOR = { category: 'door', door_type: 'single_swing', hinge: 'start', swing: 'left' }

  it('a click puts a 900 mm door centred on it, on the wall under it', () => {
    const r = doorOps(spec(), [52000, 80], [52000, 80])
    expect(r).toEqual({ ops: [{ op: 'add_opening', wall_id: 'W900', offset: 1550, width: 900, ...DOOR }] })
    expect(applyOps(spec(), (r as { ops: EditorOp[] }).ops).failed).toEqual([])
  })
  it('a click keeps 50 mm from the wall ends, narrows on a short wall, refuses a wall under 700 mm', () => {
    expect(doorOps(spec(), [57990, 0], [57990, 0])).toMatchObject({ ops: [{ wall_id: 'W903', offset: 3100 - 900 - 50 }] })
    expect(doorOps(spec(), [60400, 0], [60400, 0])).toMatchObject({ ops: [{ wall_id: 'W901', offset: 50, width: 700 }] })
    expect(doorOps(spec(), [70250, 0], [70250, 0])).toHaveProperty('error')
  })
  it('a click off every wall or on an existing opening only says so', () => {
    expect(doorOps(spec(), [52000, 1000], [52000, 1000])).toHaveProperty('error')
    expect(doorOps(spec(), [53400, 0], [53400, 0])).toMatchObject({ error: expect.stringMatching(/bukaan/) })
  })
  it('a line along a wall is the door: its ends set offset and width, in either direction', () => {
    const want = { ops: [{ op: 'add_opening', wall_id: 'W900', offset: 1000, width: 1000, ...DOOR }] }
    expect(doorOps(spec(), [51000, 100], [52000, 90])).toEqual(want)
    expect(doorOps(spec(), [52000, 90], [51000, 100])).toEqual(want)
  })
  it('a line over an existing door moves and resizes that door instead of stacking a second one', () => {
    expect(doorOps(spec(), [52900, 0], [53900, 0])).toEqual({ ops: [{ op: 'set_door', id: 'D900', offset: 2900, width: 1000 }] })
  })
  it('a line across a gap closes it with a new wall that carries the door, its ends snapped to the walls', () => {
    const r = doorOps(spec(), [54050, 30], [54850, -20])
    expect(r).toEqual({ ops: [{ op: 'add_wall', a: [54000, 0], b: [54900, 0], thickness: 150, kind: 'partition',
      openings: [{ offset: 50, width: 800, ...DOOR }] }] })
    expect(applyOps(spec(), (r as { ops: EditorOp[] }).ops).failed).toEqual([])
  })
})
