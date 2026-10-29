import { api, ApiError } from '../../api/client'
import type { ReviewTask } from '../../api/types'
import type { Spec } from '../../types/spec'
import type { EditorOp } from '../ops/reducer'
import { useEditorStore } from '../store'

type Pt = [number, number]

const END_MARGIN_MM = 50  // V008: an opening keeps 50 mm from the wall end

/**
 * Close a gap task. A door goes onto a wall the server already knows (pushOp refuses edits of unsaved elements),
 * so the wall whose b end sits at the gap is extended across it and the door is placed in the extension;
 * extending an a end would shift that wall's doors. With no b end at the gap, a new wall closes it without a door.
 */
export function closeGapOps(task: ReviewTask, withDoor: boolean, view: Spec): { ops: EditorOp[]; doorSkipped: boolean } {
  const { a, b, thickness, kind, ends = [] } = task.fix
  if (!a || !b) return { ops: [], doorSkipped: false }
  const i = ends.findIndex((e) => e.end === 'b')
  const w = i >= 0 ? view.walls?.find((x) => x.id === ends[i].wall) : undefined
  if (!w) {
    return { ops: [{ op: 'add_wall', a, b, thickness: thickness ?? 150, kind: (kind ?? 'partition') as 'partition' }], doorSkipped: withDoor }
  }
  const to = i === 0 ? b : a  // the other end of the gap
  const len = Math.round(Math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1]))
  const gap = Math.round(Math.hypot(to[0] - w.b[0], to[1] - w.b[1]))
  const ops: EditorOp[] = [{ op: 'move_wall', id: w.id, b: to }]
  if (withDoor) {
    ops.push({ op: 'add_opening', wall_id: w.id, category: 'door', offset: len, width: gap - END_MARGIN_MM,
      door_type: 'single_swing', hinge: 'start', swing: 'left' })
  }
  return { ops, doorSkipped: false }
}

/** A guide line the server snapped onto the drawing becomes one partition wall. */
export function guideLineOps(snap: { a: [number, number]; b: [number, number]; thickness: number }): EditorOp[] {
  return [{ op: 'add_wall', a: snap.a, b: snap.b, thickness: snap.thickness, kind: 'partition' }]
}

/** A rough guide line (mm) → the server snaps it onto the drawing → one wall; no double line nearby → a notice only. */
export async function snapGuide(projectId: string, a: Pt, b: Pt): Promise<void> {
  const s = useEditorStore.getState()
  try {
    const r = await api.post<{ a: Pt; b: Pt; thickness: number }>(`/api/projects/${projectId}/snap`, { a, b })
    s.applyMany(guideLineOps(r))
  } catch (e) {
    const text = e instanceof ApiError && e.code === 'no_line' ? 'Tidak ada garis ganda di dekat garis ini'
      : e instanceof ApiError && e.code === 'no_run' ? 'Belum ada gambar hasil ekstraksi untuk di-snap' : String(e)
    s.setNotice({ kind: 'warning', text })
  }
}
