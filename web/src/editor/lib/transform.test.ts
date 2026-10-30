import { describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Template } from '../../api/types'
import type { PlacedObject, Spec } from '../../types/spec'
import { deleteGeometryOps, deleteOps, duplicateOps, gizmoYawDeg, groupCenter, moveOps, rotateOps } from './transform'

const gt = gtJson as unknown as Spec
const [mx, my] = gt.rooms!.find((r) => r.name === 'R. MEETING')!.label_pos as [number, number]
const rack: Template = { id: 'rack', version: '1', name: 'Rack', category: 'rack', thumbnail_url: '', asset_url: '',
  dims: { w: 600, d: 1200, h: 2000 }, snap: { grid_mm: 600, align: 'edge' } }
const obj = (id: string, x: number, y: number, extra: Partial<PlacedObject> = {}): PlacedObject => ({
  id, template_id: 'rack', template_version: '1', position: [x, y, 0], rotation: 0, dims: [600, 1200, 2000], ...extra })

describe('transform', () => {
  it('rotateOps turns a group about its center', () => {
    const objs = [obj('O1', 0, 0), obj('O2', 2000, 0)]
    expect(groupCenter(objs)).toEqual([1000, 0])
    expect(rotateOps(objs, 90)).toEqual([
      { op: 'update_object', id: 'O1', position: [1000, -1000, 0], rotation: 90 },
      { op: 'update_object', id: 'O2', position: [1000, 1000, 0], rotation: 90 },
    ])
    expect(rotateOps([obj('O1', 0, 0, { rotation: 300 })], 90)).toMatchObject([{ rotation: 30 }])
    expect(rotateOps([obj('O1', 0, 0)], -90)).toMatchObject([{ rotation: 270 }])
  })

  it('moveOps snaps the lead object and moves the group by the same delta', () => {
    const objs = [obj('O1', 11100, 8400), obj('O2', 11700, 8400)]
    expect(moveOps(objs, [650, 10], gt, true, [rack])).toEqual([
      { op: 'update_object', id: 'O1', position: [11700, 8400, 0] },
      { op: 'update_object', id: 'O2', position: [12300, 8400, 0] },
    ])
    expect(moveOps(objs, [650, 10], gt, false, [rack])).toMatchObject([{ position: [11750, 8410, 0] }, { position: [12350, 8410, 0] }])
  })

  it('moveOps refuses to leave the room', () => {
    expect(moveOps([obj('O1', mx, my)], [-100000, 0], gt, false, [rack])).toEqual({ error: 'Objek harus tetap di dalam ruang' })
  })

  it('duplicateOps offsets by one snap step', () => {
    expect(duplicateOps([obj('O1', 100, 200, { label: 'A' })], 600)).toEqual([{ op: 'add_object', template_id: 'rack',
      template_version: '1', position: [700, 200, 0], rotation: 0, dims: [600, 1200, 2000], label: 'A' }])
    // the server rejects an explicit null on add_object fields
    expect(duplicateOps([obj('O1', 100, 200, { label: null })], 600)[0]).not.toHaveProperty('label')
  })

  it('locked objects are excluded', () => {
    const objs = [obj('O1', mx, my, { locked: true }), obj('O2', mx, my)]
    expect(deleteOps(objs)).toEqual([{ op: 'delete_object', id: 'O2' }])
    expect(rotateOps(objs, 90).map((o) => 'id' in o && o.id)).toEqual(['O2'])
    expect(duplicateOps(objs, 600)).toHaveLength(1)
    expect(moveOps(objs, [0, 0], gt, false, [rack])).toMatchObject([{ id: 'O2' }])
  })
})

describe('gizmoYawDeg', () => {
  it('the scale gizmo turns with a single object so its handles match w/d', () => {
    expect(gizmoYawDeg([obj('O1', 0, 0, { rotation: 90 })], 'scale')).toBe(90)
    expect(gizmoYawDeg([obj('O1', 0, 0, { rotation: 90 })], 'translate')).toBe(0)
    expect(gizmoYawDeg([obj('O1', 0, 0, { rotation: 90 }), obj('O2', 0, 0)], 'scale')).toBe(0)
  })

  it('deleteGeometryOps deletes picked walls, doors and stairs; a door on a deleted wall goes with its wall', () => {
    const w1 = gt.walls![0], w2 = gt.walls![1]
    const onW1 = gt.openings!.find((o) => o.wall_id === w1.id) ?? { id: 'D-x', wall_id: w1.id }
    const other = gt.openings!.find((o) => o.wall_id !== w1.id && o.wall_id !== w2.id)!
    const spec = { ...gt, openings: [...gt.openings!.filter((o) => o.id !== onW1.id), onW1] } as Spec
    const st = gt.stairs?.[0]
    const ids = [w1.id, onW1.id, other.id, w2.id, ...(st ? [st.id] : []), 'R-unknown']
    expect(deleteGeometryOps(spec, ids, 'tombol Delete')).toEqual([
      { op: 'delete_opening', id: other.id, reason: 'tombol Delete' },
      { op: 'delete_wall', id: w1.id, reason: 'tombol Delete' },
      { op: 'delete_wall', id: w2.id, reason: 'tombol Delete' },
      ...(st ? [{ op: 'delete_stair', id: st.id, reason: 'tombol Delete' }] : []),
    ])
  })
})
