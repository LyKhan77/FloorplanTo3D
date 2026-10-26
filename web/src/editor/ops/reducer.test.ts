import { describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { applyOps, type EditorOp } from './reducer'

const gt = gtJson as unknown as Spec
const meeting = gt.rooms!.find((r) => r.name === 'R. MEETING')!
const at = meeting.label_pos as [number, number]
const add: EditorOp = {
  op: 'add_object', template_id: 'rack-42u-600x1200', template_version: '1.0.0',
  position: [at[0], at[1], 0], rotation: 0, dims: [600, 1200, 2000],
}

describe('applyOps (non-geometry)', () => {
  it('add_object gets the next id and the room under its position', () => {
    const r = applyOps(gt, [add])
    expect(r.failed).toEqual([])
    expect(r.spec.objects![0].id).toBe('O1')
    expect(r.spec.objects![0].room_id).toBe(meeting.id)
    expect(r.created.O1).toBe(0)
  })

  it('ids are never reused', () => {
    const r = applyOps(gt, [add, { op: 'delete_object', id: 'O1' }, add])
    expect(r.spec.objects!.map((o) => o.id)).toEqual(['O2'])
    expect(r.created.O2).toBe(2)
  })

  it('set_wall_height "*" null clears overrides', () => {
    const r = applyOps(gt, [
      { op: 'set_wall_height', id: 'W1', height: 4500 },
      { op: 'set_wall_height', id: '*', height: null },
    ])
    expect(r.failed).toEqual([])
    expect(r.spec.walls!.every((w) => w.height === null)).toBe(true)
    expect(applyOps(gt, [{ op: 'set_wall_height', id: 'W1', height: 4500 }]).spec.walls![0].height).toBe(4500)
  })

  it('set_default wall_height and unknown key', () => {
    const r = applyOps(gt, [
      { op: 'set_default', key: 'wall_height', value: 4500 },
      { op: 'set_default', key: 'nope', value: 1 },
    ])
    expect(r.spec.meta.defaults!.wall_height).toBe(4500)
    expect(r.failed).toHaveLength(1)
    expect(r.failed[0]).toMatchObject({ index: 1, op: 'set_default' })
  })

  it('rename_room / set_room_type / update_object apply only given fields', () => {
    const r = applyOps(gt, [
      add,
      { op: 'rename_room', id: meeting.id, name: 'RAPAT' },
      { op: 'set_room_type', id: meeting.id, type: 'office' },
      { op: 'update_object', id: 'O1', label: 'A-01' },
      { op: 'update_object', id: 'O1', rotation: 90 },
    ])
    expect(r.failed).toEqual([])
    const room = r.spec.rooms!.find((x) => x.id === meeting.id)!
    expect(room.name).toBe('RAPAT')
    expect(room.type).toBe('office')
    expect(room.polygon).toEqual(meeting.polygon)
    expect(r.spec.objects![0]).toMatchObject({ label: 'A-01', rotation: 90, position: add.position, dims: add.dims })
  })

  it('update_object position recomputes room_id', () => {
    const office = gt.rooms!.find((x) => x.name === 'GUDANG')!
    const p = office.label_pos as [number, number]
    const r = applyOps(gt, [add, { op: 'update_object', id: 'O1', position: [p[0], p[1], 0] }])
    expect(r.spec.objects![0].room_id).toBe(office.id)
  })

  it('missing target fails that op only and base stays untouched', () => {
    const before = JSON.stringify(gt)
    const r = applyOps(gt, [
      { op: 'update_object', id: 'O99', rotation: 90 },
      { op: 'rename_room', id: 'R999', name: 'x' },
      add,
      { op: 'add_stair', flights: [{ start: [0, 0], end: [0, 1000], width: 1000, risers: 10 }] },
    ])
    expect(r.failed.map((f) => f.index)).toEqual([0, 1, 3])
    expect(r.failed[2].message).toBe('tidak tersedia di editor')
    expect(r.spec.objects).toHaveLength(1)
    expect(JSON.stringify(gt)).toBe(before)
  })
})
