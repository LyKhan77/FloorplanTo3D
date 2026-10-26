import type { Spec } from '../../types/spec'
import { allIds } from './ids'
import { applyOps, type EditorOp, type OpFailure } from './reducer'

/**
 * Local ops never reference an ID the base spec does not have: the server only allocates new IDs on Save, so
 * after a 409 rebase a predicted ID could point at another tab's element. Edits of unsaved elements are folded
 * into the op that creates them, or rejected.
 */
export function targetIds(op: EditorOp): string[] {
  if (op.op === 'merge_walls') return op.ids
  if (op.op === 'add_opening') return [op.wall_id]
  if ('id' in op && op.id !== '*') return [op.id]
  return []
}

const COALESCE = new Set(['update_object', 'move_wall', 'set_door', 'set_stair', 'set_wall_height', 'set_room_type', 'rename_room'])
const FOLD: Record<string, { creator: string; fields?: string[] }> = {
  update_object: { creator: 'add_object', fields: ['position', 'rotation', 'dims', 'label'] },
  delete_object: { creator: 'add_object' },
  move_wall: { creator: 'add_wall', fields: ['a', 'b', 'thickness', 'kind'] },
  delete_wall: { creator: 'add_wall' },
  set_door: { creator: 'add_opening', fields: ['door_type', 'hinge', 'swing', 'width', 'offset', 'height'] },
  delete_opening: { creator: 'add_opening' },
}

export function pushOp(base: Spec, ops: EditorOp[], op: EditorOp): { ops: EditorOp[] } | { error: string } {
  const known = new Set(allIds(base))
  const predicted = targetIds(op).filter((id) => !known.has(id))
  if (predicted.length === 0) {
    const last = ops.at(-1)
    if (last && last.op === op.op && COALESCE.has(op.op) && 'id' in last && 'id' in op && last.id === op.id) {
      const merged = { ...last, ...op } as EditorOp
      // identical re-fire (e.g. a widget echoing its value): keep the same list so nothing re-renders
      return { ops: JSON.stringify(merged) === JSON.stringify(last) ? ops : [...ops.slice(0, -1), merged] }
    }
    return { ops: [...ops, op] }
  }
  const id = predicted[0]
  const k = applyOps(base, ops).created[id]
  const rule = FOLD[op.op]
  if (k === undefined) return { error: `unknown id ${id}` }
  if (!rule || predicted.length > 1 || ops[k].op !== rule.creator) return { error: `Save dulu: ${id} belum disimpan` }
  if (op.op === 'update_object' && op.locked != null) return { error: 'Save dulu sebelum mengunci objek baru' }
  if (!rule.fields) return { ops: ops.filter((_, i) => i !== k) }
  const patch = Object.fromEntries(Object.entries(op).filter(([f, v]) => rule.fields!.includes(f) && v !== undefined))
  // a creation op takes "absent" for cleared fields: the server refuses explicit nulls on add_* ops
  const merge = (o: EditorOp) => Object.fromEntries(Object.entries({ ...o, ...patch }).filter(([, v]) => v !== null)) as EditorOp
  return { ops: ops.map((o, i) => (i === k ? merge(o) : o)) }
}

/** What fails if the local ops are replayed on `head` (another tab saved first). */
export function rebasePreview(head: Spec, ops: EditorOp[]): OpFailure[] {
  const known = new Set(allIds(head))
  const failed = new Map(applyOps(head, ops).failed.map((f) => [f.index, f]))
  ops.forEach((op, index) => {
    const gone = targetIds(op).filter((id) => !known.has(id))
    if (gone.length && !failed.has(index)) failed.set(index, { index, op: op.op, message: `${gone.join(', ')} sudah tidak ada` })
  })
  return [...failed.values()].sort((a, b) => a.index - b.index)
}
