import type { Template } from '../../api/types'
import type { Spec } from '../../types/spec'
import type { EditorOp } from '../ops/reducer'
import { roomAt } from './geom'
import { snapPosition } from './snap'

const DEFAULT_SNAP = { grid_mm: 600, align: 'edge' as const }

/** add_object for a template dropped at plan point p (mm); outside every room is refused. */
export function planDrop(view: Spec, t: Template, p: [number, number], snapOn: boolean):
  { op: EditorOp; warning?: string } | { error: string } {
  const dims: [number, number, number] = [t.dims.w, t.dims.d, t.dims.h]
  const [x, y] = snapPosition(p, dims, 0, t.snap ?? DEFAULT_SNAP, snapOn)
  const roomId = roomAt(view, x, y)
  if (roomId === null) return { error: 'Objek harus diletakkan di dalam ruang' }
  const op: EditorOp = { op: 'add_object', template_id: t.id, template_version: t.version, position: [x, y, 0], rotation: 0, dims }
  const type = view.rooms?.find((r) => r.id === roomId)?.type
  const allowed = t.allowed_room_types ?? []
  if (allowed.length && type && !allowed.includes(type)) {
    return { op, warning: `Template ini tidak dianjurkan untuk tipe ruang ${type}` }
  }
  return { op }
}
