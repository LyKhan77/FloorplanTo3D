import { describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { allIds } from './ids'
import { pushOp, targetIds } from './compose'
import { applyOps, type EditorOp } from './reducer'

const gt = gtJson as unknown as Spec
const rooms = gt.rooms!.filter((r) => r.label_pos)
const addAt = (i: number): EditorOp => {
  const [x, y] = rooms[i % rooms.length].label_pos as [number, number]
  return { op: 'add_object', template_id: 'rack-42u-600x1200', template_version: '1.0.0', position: [x, y, 0],
    rotation: 0, dims: [600, 1200, 2000] }
}

function push(base: Spec, ops: EditorOp[], op: EditorOp): EditorOp[] {
  const r = pushOp(base, ops, op)
  if ('error' in r) throw new Error(r.error)
  return r.ops
}

describe('pushOp', () => {
  it('folds edits of unsaved elements into their creation op', () => {
    let ops = push(gt, [], addAt(0))
    ops = push(gt, ops, { op: 'update_object', id: 'O1', position: [1000, 2000, 0], rotation: 90 })
    expect(ops).toEqual([{ ...addAt(0), position: [1000, 2000, 0], rotation: 90 }])
    expect(push(gt, ops, { op: 'delete_object', id: 'O1' })).toEqual([])

    const addDoor: EditorOp = { op: 'add_opening', wall_id: 'W1', category: 'door', offset: 1000, width: 900 }
    ops = push(gt, [addDoor], { op: 'set_door', id: 'D20', width: 1000 })
    expect(ops).toEqual([{ ...addDoor, width: 1000 }])
    expect(push(gt, ops, { op: 'delete_opening', id: 'D20', reason: 'x' })).toEqual([])

    const addWall: EditorOp = { op: 'add_wall', a: [0, 0], b: [3000, 0], thickness: 150, kind: 'partition' }
    ops = push(gt, [addWall], { op: 'move_wall', id: 'W78', b: [4000, 0] })
    expect(ops).toEqual([{ ...addWall, b: [4000, 0] }])
    expect(push(gt, ops, { op: 'delete_wall', id: 'W78', reason: 'x' })).toEqual([])
  })

  it('rejects ops that would reference a predicted id', () => {
    const addWall: EditorOp = { op: 'add_wall', a: [0, 0], b: [3000, 0], thickness: 150, kind: 'partition' }
    const split = pushOp(gt, [addWall], { op: 'split_wall', id: 'W78', at_offset: 1000 })
    expect('error' in split && split.error).toContain('belum disimpan')
    const door = pushOp(gt, [addWall], { op: 'add_opening', wall_id: 'W78', category: 'door', offset: 100, width: 900 })
    expect('error' in door && door.error).toContain('belum disimpan')
    const lock = pushOp(gt, [addAt(0)], { op: 'update_object', id: 'O1', locked: true })
    expect('error' in lock && lock.error).toContain('Save dulu')
    const piece = pushOp(gt, [{ op: 'split_wall', id: 'W1', at_offset: 1000 }], { op: 'move_wall', id: 'W78', b: [0, 0] })
    expect('error' in piece && piece.error).toContain('belum disimpan')
  })

  it('coalesces consecutive updates of the same base element', () => {
    let ops = push(gt, [], { op: 'set_wall_height', id: 'W1', height: 4000 })
    ops = push(gt, ops, { op: 'set_wall_height', id: 'W1', height: 4500 })
    expect(ops).toEqual([{ op: 'set_wall_height', id: 'W1', height: 4500 }])
    ops = push(gt, ops, { op: 'set_wall_height', id: 'W2', height: 4500 })
    expect(ops).toHaveLength(2)
  })

  it('no op in the list ever targets a predicted id', () => {
    const base = applyOps(gt, [addAt(0), addAt(1), addAt(2)]).spec
    const known = new Set(allIds(base))
    let seed = 7
    const rnd = (n: number) => ((seed = (seed * 1103515245 + 12345) % 2147483648) % n)
    let ops: EditorOp[] = []
    for (let i = 0; i < 200; i++) {
      const visible = (applyOps(base, ops).spec.objects ?? []).map((o) => o.id)
      const kind = visible.length ? rnd(3) : 0
      const id = visible[rnd(Math.max(visible.length, 1))]
      const op: EditorOp = kind === 0 ? addAt(rnd(20))
        : kind === 1 ? { op: 'update_object', id, position: (addAt(rnd(20)) as { position: [number, number, number] }).position }
        : { op: 'delete_object', id }
      ops = push(base, ops, op)
      for (const o of ops) for (const t of targetIds(o)) expect(known.has(t)).toBe(true)
      expect(applyOps(base, ops).failed).toEqual([])
    }
  })
})
