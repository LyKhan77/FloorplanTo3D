import { beforeEach, describe, expect, it } from 'vitest'
import gtJson from '../../../benchmarks/gatsu/gt_spec.json'
import type { AddObject } from '../types/ops'
import type { Spec } from '../types/spec'
import { deleteOps } from './lib/transform'
import { rebasePreview } from './ops/compose'
import { applyOps, type EditorOp } from './ops/reducer'
import { useEditorStore } from './store'

const gt = gtJson as unknown as Spec
const [px, py] = gt.rooms!.find((r) => r.name === 'R. MEETING')!.label_pos as [number, number]
const add = (dx = 0): AddObject => ({ op: 'add_object', template_id: 'rack-42u-600x1200', template_version: '1.0.0',
  position: [px + dx, py, 0], rotation: 0, dims: [600, 1200, 2000] })
const st = () => useEditorStore.getState()

describe('useEditorStore', () => {
  beforeEach(() => st().load('p-1', gt))

  it('undo/redo walk the op list and cap at 100', () => {
    for (let i = 0; i < 105; i++) expect(st().apply(add(i))).toBe(true)
    expect(st().ops).toHaveLength(105)
    expect(st().past).toHaveLength(100)
    st().undo()
    st().undo()
    expect(st().ops).toHaveLength(103)
    expect(st().view!.objects).toHaveLength(103)
    st().redo()
    expect(st().ops).toHaveLength(104)
    st().apply(add(999))
    expect(st().future).toEqual([])
  })

  it('apply returns false and sets a notice on a rejected op', () => {
    st().apply({ op: 'add_wall', a: [0, 0], b: [3000, 0], thickness: 150, kind: 'partition' })
    expect(st().apply({ op: 'split_wall', id: 'W78', at_offset: 1000 })).toBe(false)
    expect(st().notice).toMatchObject({ kind: 'error' })
    expect(st().ops).toHaveLength(1)
    expect(st().apply({ op: 'set_door', id: 'D999', width: 1000 })).toBe(false)
    expect(st().ops).toHaveLength(1)
    expect(st().apply(add(0))).toBe(true)
    expect(st().notice).toBeNull()
  })

  it('applyMany is one undo step and all-or-nothing', () => {
    expect(st().applyMany([add(0), add(100)])).toBe(true)
    expect(st().past).toHaveLength(1)
    expect(st().applyMany([add(200), { op: 'update_object', id: 'O3', locked: true }])).toBe(false)
    expect(st().ops).toHaveLength(2)
  })

  it('re-applying an identical op changes nothing (no history step, no new view)', () => {
    st().apply({ op: 'set_room_type', id: 'R1', type: 'office' })
    const view = st().view
    expect(st().apply({ op: 'set_room_type', id: 'R1', type: 'office' })).toBe(true)
    expect(st().past).toHaveLength(1)
    expect(st().view).toBe(view)
  })

  it('a camera focus request is taken once (a mode switch must not replay it)', () => {
    st().setFocus([1000, 2000])
    expect(st().takeFocus()).toEqual([1000, 2000])
    expect(st().takeFocus()).toBeNull()
  })

  it('deleting several unsaved objects removes exactly those (no renumbering mid-batch)', () => {
    st().applyMany([add(0), add(1000), add(2000)])
    const [a, b] = st().view!.objects!
    expect(st().applyMany(deleteOps([a, b]))).toBe(true)
    expect(st().view!.objects!.map((o) => o.position[0])).toEqual([px + 2000])
    st().load('p-1', gt)
    st().applyMany([add(0), add(1000)])
    expect(st().applyMany(deleteOps(st().view!.objects!))).toBe(true)
    expect(st().ops).toEqual([])
  })

  it('refuses edits while a save is in flight', () => {
    st().apply(add(0))
    st().setSaving(true)
    expect(st().apply(add(100))).toBe(false)
    expect(st().notice?.text).toContain('menyimpan')
    st().undo()
    expect(st().ops).toHaveLength(1)
    st().setSaving(false)
    expect(st().apply(add(100))).toBe(true)
  })

  it('accepting a rebase drops selected predicted ids (they may name the other tab\'s element now)', () => {
    st().apply(add(0))
    st().select(['O1', 'W1'])
    const head = applyOps(gt, [{ ...add(0), position: [px + 1234, py, 0] }]).spec
    st().acceptRebase(head, [])
    expect(st().selection).toEqual(['W1'])
  })

  it('drops selected ids that no longer exist', () => {
    st().applyMany([add(0), add(100)])
    st().select(['O2'])
    st().apply({ op: 'delete_object', id: 'O1' })
    expect(st().selection).toEqual([])
  })

  it('rebase lists ops whose target vanished and never touches the other tab\'s new object', () => {
    const doomed = gt.walls!.find((w) => !gt.openings!.some((o) => o.wall_id === w.id))!.id
    const other: EditorOp = { ...add(0), position: [px + 1234, py, 0] }
    const head = applyOps(gt, [other, { op: 'delete_opening', id: 'D1', reason: 'x' },
      { op: 'delete_wall', id: doomed, reason: 'x' }]).spec
    st().apply(add(0))
    st().apply({ op: 'set_door', id: 'D1', width: 1000 })
    st().apply({ op: 'set_wall_height', id: doomed, height: 4500 })
    const opsBefore = st().ops
    const failed = rebasePreview(head, st().ops)
    expect(failed.map((f) => f.index)).toEqual([1, 2])
    expect(st().ops).toBe(opsBefore)
    st().acceptRebase(head, failed.map((f) => f.index))
    const objs = st().view!.objects!
    expect(objs.map((o) => o.id)).toEqual(['O1', 'O2'])
    expect(objs[0].position).toEqual([px + 1234, py, 0])
    expect(objs[1].position).toEqual([px, py, 0])
    expect(st().failed).toEqual([])
  })

  it('markSaved clears ops, history and sets the new base', () => {
    st().apply(add(0))
    st().undo()
    st().redo()
    const saved = { ...applyOps(gt, st().ops).spec, meta: { ...gt.meta, version: 2 } }
    st().markSaved(saved)
    expect(st()).toMatchObject({ ops: [], past: [], future: [], baseVersion: 2, base: saved, view: saved })
  })
})
