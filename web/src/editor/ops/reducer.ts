import type { SpecOpsSchema } from '../../types/ops'
import type { Defaults, Spec, Wall } from '../../types/spec'
import { roomAt, roundHalfEven } from '../lib/geom'
import { compareIds, seedIdSeq, takeId } from './ids'

/** Client mirror of core/spec/ops.py. Rooms are not rebuilt here: the server recomputes them on Save. */
export type EditorOp = SpecOpsSchema[number]
export interface OpFailure { index: number; op: string; message: string }
export interface ApplyResult { spec: Spec; failed: OpFailure[]; created: Record<string, number> }

const DEFAULT_KEYS: (keyof Defaults)[] = [
  'wall_height', 'wall_thickness', 'door_height', 'window_sill', 'window_height', 'floor_to_floor',
]

function find<T extends { id: string }>(items: T[] | undefined, id: string): T {
  const it = items?.find((x) => x.id === id)
  if (!it) throw new Error(`unknown id ${id}`)
  return it
}

/** The fields an op actually carries, minus its op name and target id ("leave unchanged" = absent). */
function given(op: object, skip: string[] = ['op', 'id']): Record<string, unknown> {
  return Object.fromEntries(Object.entries(op).filter(([k, v]) => !skip.includes(k) && v !== undefined))
}

const PARALLEL_TOL = Math.sin((1.5 * Math.PI) / 180)

function unit(w: Wall): [number, number, number] {
  const dx = w.b[0] - w.a[0], dy = w.b[1] - w.a[1]
  const length = Math.hypot(dx, dy)
  if (length === 0) throw new Error(`wall ${w.id} has zero length`)
  return [dx / length, dy / length, length]
}

const pt = (x: number, y: number): [number, number] => [roundHalfEven(x), roundHalfEven(y)]
const MIRROR: Record<string, string> = { start: 'end', end: 'start', left: 'right', right: 'left' }

function mergeWalls(s: Spec, ids: string[]): void {
  const walls = ids.map((id) => find(s.walls, id))
  const keep = walls.reduce((a, b) => (compareIds(b.id, a.id) < 0 ? b : a))
  const [ux, uy] = unit(keep)
  const maxT = Math.max(...walls.map((w) => w.thickness))
  const along = (p: number[]) => (p[0] - keep.a[0]) * ux + (p[1] - keep.a[1]) * uy
  for (const w of walls) {
    const [wx, wy] = unit(w)
    if (Math.abs(wx * uy - wy * ux) > PARALLEL_TOL) throw new Error(`wall ${w.id} is not parallel to ${keep.id}`)
    for (const p of [w.a, w.b]) {
      if (Math.abs((p[0] - keep.a[0]) * uy - (p[1] - keep.a[1]) * ux) > maxT) {
        throw new Error(`wall ${w.id} is not collinear with ${keep.id}`)
      }
    }
  }
  const ts = walls.flatMap((w) => [along(w.a), along(w.b)])
  const t0 = Math.min(...ts), t1 = Math.max(...ts)
  for (const o of s.openings ?? []) {
    const w = walls.find((x) => x.id === o.wall_id)
    if (!w) continue
    const [wx, wy] = unit(w)
    const ends = [o.offset, o.offset + o.width].map((d) => along([w.a[0] + wx * d, w.a[1] + wy * d]))
    o.wall_id = keep.id
    o.offset = roundHalfEven(Math.min(...ends) - t0)
    if (wx * ux + wy * uy < 0) { // hinge/swing are relative to a->b; a reversed wall mirrors them
      if (o.hinge) o.hinge = (MIRROR[o.hinge] ?? o.hinge) as typeof o.hinge
      if (o.swing) o.swing = MIRROR[o.swing] as typeof o.swing
    }
  }
  const a0 = [...keep.a]
  keep.a = pt(a0[0] + ux * t0, a0[1] + uy * t0)
  keep.b = pt(a0[0] + ux * t1, a0[1] + uy * t1)
  s.walls = s.walls!.filter((w) => w === keep || !walls.includes(w))
}

function splitWall(s: Spec, id: string, at: number): string {
  const w = find(s.walls, id)
  const [ux, uy, length] = unit(w)
  if (!(at > 0 && at < length)) throw new Error(`at_offset ${at} outside wall ${w.id} (length ${length.toFixed(0)})`)
  const onWall = (s.openings ?? []).filter((o) => o.wall_id === w.id)
  if (onWall.some((o) => o.offset < at && at < o.offset + o.width)) throw new Error(`split at ${at} crosses an opening`)
  const p = pt(w.a[0] + ux * at, w.a[1] + uy * at)
  const nid = takeId(s, 'W')
  s.walls!.push({ ...structuredClone(w), id: nid, a: p, b: [...w.b] })
  w.b = p
  for (const o of onWall) {
    if (o.offset >= at) {
      o.wall_id = nid
      o.offset -= at
    }
  }
  return nid
}

function step(s: Spec, op: EditorOp, index: number, created: Record<string, number>): void {
  switch (op.op) {
    case 'add_object': {
      const id = takeId(s, 'O')
      const [x, y] = op.position
      ;(s.objects ??= []).push({
        id, template_id: op.template_id, template_version: op.template_version, position: op.position,
        rotation: op.rotation ?? 0, dims: op.dims, room_id: roomAt(s, x, y), label: op.label ?? null, locked: false,
      })
      created[id] = index
      return
    }
    case 'update_object': {
      const o = find(s.objects, op.id)
      Object.assign(o, given(op))
      if (op.position) o.room_id = roomAt(s, op.position[0], op.position[1])
      return
    }
    case 'delete_object':
      s.objects = s.objects!.filter((o) => o !== find(s.objects, op.id))
      return
    case 'set_wall_height':
      for (const w of op.id === '*' ? (s.walls ?? []) : [find(s.walls, op.id)]) w.height = op.height
      return
    case 'set_default':
      if (!DEFAULT_KEYS.includes(op.key as keyof Defaults)) throw new Error(`unknown default ${op.key}`)
      s.meta.defaults = { ...s.meta.defaults, [op.key]: op.value }
      return
    case 'rename_room':
      find(s.rooms, op.id).name = op.name
      return
    case 'set_room_type':
      find(s.rooms, op.id).type = op.type
      return
    case 'delete_wall':
      find(s.walls, op.id)
      s.walls = s.walls!.filter((w) => w.id !== op.id)
      s.openings = (s.openings ?? []).filter((o) => o.wall_id !== op.id)
      return
    case 'merge_walls':
      mergeWalls(s, op.ids)
      return
    case 'split_wall':
      created[splitWall(s, op.id, op.at_offset)] = index
      return
    case 'move_wall':
      Object.assign(find(s.walls, op.id), given(op))
      return
    case 'add_wall': {
      const id = takeId(s, 'W')
      ;(s.walls ??= []).push({
        id, a: op.a, b: op.b, thickness: op.thickness, kind: op.kind, height: null, base_z: 0, grid_ref: [],
        free_ends: false, allow_skew: false,
      })
      created[id] = index
      for (const o of op.openings ?? []) step(s, { ...o, op: 'add_opening', wall_id: id }, index, created)
      return
    }
    case 'set_door': {
      const d = find(s.openings, op.id)
      if (d.category !== 'door') throw new Error(`${op.id} is not a door`)
      Object.assign(d, given(op))
      return
    }
    case 'delete_opening':
      find(s.openings, op.id)
      s.openings = s.openings!.filter((o) => o.id !== op.id)
      return
    case 'add_opening': {
      find(s.walls, op.wall_id)
      const id = takeId(s, op.category === 'door' ? 'D' : 'N')
      const sill = op.sill ?? (op.category === 'window' ? (s.meta.defaults?.window_sill ?? 900) : 0)
      ;(s.openings ??= []).push({
        height: null, door_type: null, hinge: null, swing: null, leaf_split: null, ...given(op, ['op']),
        id, category: op.category, wall_id: op.wall_id, offset: op.offset, width: op.width, sill,
      })
      created[id] = index
      return
    }
    case 'set_stair':
      Object.assign(find(s.stairs, op.id), given(op))
      return
    case 'delete_stair':
      find(s.stairs, op.id)
      s.stairs = s.stairs!.filter((x) => x.id !== op.id)
      return
    case 'add_stair':
      throw new Error('tidak tersedia di editor')
  }
}

/** Pure: never mutates `base`. A failing op is skipped (the server is atomic), later ops still apply. */
export function applyOps(base: Spec, ops: EditorOp[]): ApplyResult {
  const spec = structuredClone(base)
  seedIdSeq(spec)
  const failed: OpFailure[] = []
  const created: Record<string, number> = {}
  ops.forEach((op, index) => {
    try {
      step(spec, op, index, created)
    } catch (e) {
      failed.push({ index, op: op.op, message: (e as Error).message })
    }
  })
  return { spec, failed, created }
}
