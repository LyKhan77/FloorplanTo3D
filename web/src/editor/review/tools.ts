import { api, ApiError } from '../../api/client'
import type { ReviewTask } from '../../api/types'
import type { Spec } from '../../types/spec'
import type { EditorOp } from '../ops/reducer'
import { useEditorStore } from '../store'

type Pt = [number, number]

const END_MARGIN_MM = 50  // V008: an opening keeps 50 mm from the wall end
const DOOR_MIN_MM = 600  // V010's narrowest door

/**
 * Close a gap task. A door goes onto a wall the server already knows (pushOp refuses edits of unsaved elements),
 * so the wall whose b end sits at the gap is extended across it and the door is placed in the extension;
 * extending an a end would shift that wall's doors. With no b end at the gap, a new wall closes it without a door.
 */
export type DoorSkipped = null | 'needs-save' | 'too-narrow'

export function closeGapOps(task: ReviewTask, withDoor: boolean, view: Spec): { ops: EditorOp[]; doorSkipped: DoorSkipped } {
  const { a, b, thickness, kind, ends = [] } = task.fix
  if (!a || !b) return { ops: [], doorSkipped: null }
  const i = ends.findIndex((e) => e.end === 'b')
  const w = i >= 0 ? view.walls?.find((x) => x.id === ends[i].wall) : undefined
  if (!w) {
    return { ops: [{ op: 'add_wall', a, b, thickness: thickness ?? 150, kind: (kind ?? 'partition') as 'partition' }],
      doorSkipped: withDoor ? 'needs-save' : null }
  }
  const to = i === 0 ? b : a  // the other end of the gap
  const len = Math.ceil(Math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1]))
  // the door spans the extension and keeps V008's 50 mm from the new end; the real new length, not len + gap
  const width = Math.floor(Math.hypot(to[0] - w.a[0], to[1] - w.a[1]) - len - END_MARGIN_MM)
  const ops: EditorOp[] = [{ op: 'move_wall', id: w.id, b: to }]
  if (withDoor && width >= DOOR_MIN_MM) {
    ops.push({ op: 'add_opening', wall_id: w.id, category: 'door', offset: len, width,
      door_type: 'single_swing', hinge: 'start', swing: 'left' })
  }
  return { ops, doorSkipped: withDoor && width < DOOR_MIN_MM ? 'too-narrow' : null }
}

const DOOR_MM = 900
const HIT_MM = 300  // a click this close to a wall's centre line lands on it

/** "Pintu baru": a 900 mm single door centred on the click, on the nearest wall; narrower on a short wall; null when
 *  the click is off every wall or the wall cannot hold 600 mm plus V008's end margins. */
export function doorAtOps(view: Spec, p: Pt): EditorOp | null {
  let best: { id: string; len: number; t: number; d: number } | null = null
  for (const w of view.walls ?? []) {
    const dx = w.b[0] - w.a[0], dy = w.b[1] - w.a[1], len = Math.hypot(dx, dy)
    if (!len) continue
    const t = Math.min(len, Math.max(0, ((p[0] - w.a[0]) * dx + (p[1] - w.a[1]) * dy) / len))
    const d = Math.hypot(w.a[0] + (dx * t) / len - p[0], w.a[1] + (dy * t) / len - p[1])
    if (d <= HIT_MM && (!best || d < best.d)) best = { id: w.id, len, t, d }
  }
  if (!best) return null
  const room = Math.floor(best.len) - 2 * END_MARGIN_MM
  const width = Math.min(DOOR_MM, room)
  if (width < DOOR_MIN_MM) return null
  const offset = Math.round(Math.min(room - width, Math.max(0, best.t - width / 2 - END_MARGIN_MM))) + END_MARGIN_MM
  return { op: 'add_opening', wall_id: best.id, category: 'door', offset, width, door_type: 'single_swing', hinge: 'start', swing: 'left' }
}

export const DOOR_SKIPPED_TEXT: Record<Exclude<DoorSkipped, null>, string> = {
  'needs-save': 'Celah ditutup; pintu bisa ditambahkan setelah Simpan',
  'too-narrow': 'Celah ditutup tanpa pintu: terlalu sempit untuk pintu (< 600 mm)',
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
