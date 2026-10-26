import type { Template } from '../../api/types'
import type { PlacedObject, Spec } from '../../types/spec'
import type { EditorOp } from '../ops/reducer'
import { roomAt, roundHalfEven } from './geom'
import { snapPosition } from './snap'

const DEFAULT_SNAP = { grid_mm: 600, align: 'edge' as const }
export const unlocked = (objs: PlacedObject[]) => objs.filter((o) => !o.locked)
export const templateOf = (o: PlacedObject, templates: Template[]) =>
  templates.find((t) => t.id === o.template_id && t.version === o.template_version)

export function groupCenter(objs: PlacedObject[]): [number, number] {
  const n = objs.length || 1
  return [objs.reduce((s, o) => s + o.position[0], 0) / n, objs.reduce((s, o) => s + o.position[1], 0) / n]
}

/** The lead (first) object snaps; the whole group moves by the lead's snapped delta and must stay inside rooms. */
export function moveOps(objs: PlacedObject[], delta: [number, number], view: Spec, snapOn: boolean, templates: Template[]):
  EditorOp[] | { error: string } {
  const free = unlocked(objs)
  if (!free.length) return []
  const lead = free[0]
  const target: [number, number] = [lead.position[0] + delta[0], lead.position[1] + delta[1]]
  const [sx, sy] = snapPosition(target, lead.dims as [number, number, number], lead.rotation ?? 0,
    templateOf(lead, templates)?.snap ?? DEFAULT_SNAP, snapOn)
  const dx = roundHalfEven(sx - lead.position[0]), dy = roundHalfEven(sy - lead.position[1])
  const ops: EditorOp[] = []
  for (const o of free) {
    const [x, y, z] = [o.position[0] + dx, o.position[1] + dy, o.position[2]]
    if (roomAt(view, x, y) === null) return { error: 'Objek harus tetap di dalam ruang' }
    ops.push({ op: 'update_object', id: o.id, position: [x, y, z] })
  }
  return ops
}

const norm = (deg: number) => ((deg % 360) + 360) % 360

export function rotateOps(objs: PlacedObject[], deg: number): EditorOp[] {
  const free = unlocked(objs)
  const [cx, cy] = groupCenter(free)
  const c = Math.cos((deg * Math.PI) / 180), s = Math.sin((deg * Math.PI) / 180)
  return free.map((o) => {
    const dx = o.position[0] - cx, dy = o.position[1] - cy
    return { op: 'update_object', id: o.id, rotation: norm((o.rotation ?? 0) + deg),
      position: [roundHalfEven(cx + dx * c - dy * s) + 0, roundHalfEven(cy + dx * s + dy * c) + 0, o.position[2]] }
  })
}

export function duplicateOps(objs: PlacedObject[], stepMm: number): EditorOp[] {
  return unlocked(objs).map((o) => ({
    op: 'add_object', template_id: o.template_id, template_version: o.template_version,
    position: [o.position[0] + stepMm, o.position[1], o.position[2]], rotation: o.rotation ?? 0, dims: o.dims,
    ...(o.label != null ? { label: o.label } : {}), // add_object refuses an explicit null
  }))
}

export const deleteOps = (objs: PlacedObject[]): EditorOp[] => unlocked(objs).map((o) => ({ op: 'delete_object', id: o.id }))
