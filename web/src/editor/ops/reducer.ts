import type { SpecOpsSchema } from '../../types/ops'
import type { Defaults, Spec } from '../../types/spec'
import { roomAt } from '../lib/geom'
import { seedIdSeq, takeId } from './ids'

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
    case 'add_stair':
      throw new Error('tidak tersedia di editor')
    default:
      throw new Error('unsupported')
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
