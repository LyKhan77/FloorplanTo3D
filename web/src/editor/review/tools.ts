import { api, ApiError } from '../../api/client'
import type { ReviewTask } from '../../api/types'
import type { Spec } from '../../types/spec'
import type { EditorOp } from '../ops/reducer'
import { useEditorStore } from '../store'

type Pt = [number, number]

const END_MARGIN_MM = 50  // V008: an opening keeps 50 mm from the wall end
const DOOR_MIN_MM = 600  // V010's narrowest door

/**
 * Close a gap task. The wall whose b end sits at the gap is extended across it and the door is placed in the
 * extension; extending an a end would shift that wall's doors. With no b end at the gap, a new wall closes it and
 * carries the door in its add_wall op (an unsaved wall has no ID to point at).
 */
export type DoorSkipped = null | 'too-narrow'

export function closeGapOps(task: ReviewTask, withDoor: boolean, view: Spec): { ops: EditorOp[]; doorSkipped: DoorSkipped } {
  const { a, b, thickness, kind, ends = [] } = task.fix
  if (!a || !b) return { ops: [], doorSkipped: null }
  const i = ends.findIndex((e) => e.end === 'b')
  const w = i >= 0 ? view.walls?.find((x) => x.id === ends[i].wall) : undefined
  if (!w) {
    // the door rides on the new wall's add_wall, keeping V008's margin at both ends
    const width = Math.floor(Math.hypot(b[0] - a[0], b[1] - a[1])) - 2 * END_MARGIN_MM
    const door = withDoor && width >= DOOR_MIN_MM
    return { ops: [{ op: 'add_wall', a, b, thickness: thickness ?? 150, kind: (kind ?? 'partition') as 'partition',
      ...(door ? { openings: [{ category: 'door' as const, offset: END_MARGIN_MM, width, door_type: 'single_swing' as const, hinge: 'start' as const, swing: 'left' as const }] } : {}) }],
      doorSkipped: withDoor && !door ? 'too-narrow' : null }
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
const LINE_HIT_MM = 400  // a door line's midpoint this close to a roughly parallel wall lies on it
const PARALLEL = Math.cos((15 * Math.PI) / 180)
const CLICK_MM = 300  // a shorter drag is a click
const DOOR = { category: 'door' as const, door_type: 'single_swing' as const, hinge: 'start' as const, swing: 'left' as const }

type Hit = { id: string; a: Pt; len: number; u: Pt; d: number }
const along = (h: Hit, p: Pt) => (p[0] - h.a[0]) * h.u[0] + (p[1] - h.a[1]) * h.u[1]

/** Nearest wall to p within `max` mm whose direction is within 15 degrees of `dir` (any wall when dir is null). */
function nearestWall(view: Spec, p: Pt, max: number, dir: Pt | null): Hit | null {
  let best: Hit | null = null
  for (const w of view.walls ?? []) {
    const len = Math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1])
    if (!len) continue
    const h: Hit = { id: w.id, a: w.a as Pt, len, u: [(w.b[0] - w.a[0]) / len, (w.b[1] - w.a[1]) / len], d: 0 }
    if (dir && Math.abs(dir[0] * h.u[0] + dir[1] * h.u[1]) < PARALLEL) continue
    const t = Math.min(len, Math.max(0, along(h, p)))
    h.d = Math.hypot(h.a[0] + h.u[0] * t - p[0], h.a[1] + h.u[1] * t - p[1])
    if (h.d <= max && (!best || h.d < best.d)) best = h
  }
  return best
}

/** A gap door's wall end: the nearest wall end within reach, else the nearest point on a wall, else where drawn. */
function snapEnd(view: Spec, p: Pt): Pt {
  const ends = (view.walls ?? []).flatMap((w) => [w.a, w.b] as Pt[])
  const end = ends.reduce<Pt | null>((b, e) => (Math.hypot(e[0] - p[0], e[1] - p[1]) <= LINE_HIT_MM
    && (!b || Math.hypot(e[0] - p[0], e[1] - p[1]) < Math.hypot(b[0] - p[0], b[1] - p[1])) ? e : b), null)
  if (end) return [end[0], end[1]]
  const h = nearestWall(view, p, LINE_HIT_MM, null)
  if (!h) return [Math.round(p[0]), Math.round(p[1])]
  const t = Math.min(h.len, Math.max(0, along(h, p)))
  return [Math.round(h.a[0] + h.u[0] * t), Math.round(h.a[1] + h.u[1] * t)]
}

/**
 * "Pintu" tool. A click puts a 900 mm door centred on the wall under it. A line (hinge side to the far jamb) is the
 * door: along a wall it sets offset and width, over an existing door it moves and resizes that door, and across a
 * gap it becomes a new wall carrying the door. V008's 50 mm end margins hold; nothing stacks on another opening.
 */
export function doorOps(view: Spec, a: Pt, b: Pt, thickness = 150): { ops: EditorOp[] } | { error: string } {
  const len = Math.hypot(b[0] - a[0], b[1] - a[1])
  const click = len < CLICK_MM
  const mid: Pt = click ? a : [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
  const h = nearestWall(view, mid, click ? HIT_MM : LINE_HIT_MM, click ? null : [(b[0] - a[0]) / len, (b[1] - a[1]) / len])
  if (!h && click) return { error: 'Klik di atas dinding, atau tarik garis pintu' }
  const lo0 = END_MARGIN_MM, hi0 = Math.floor(h?.len ?? 0) - END_MARGIN_MM
  let lo: number, hi: number
  if (click) {
    const width = Math.min(DOOR_MM, hi0 - lo0)
    if (width < DOOR_MIN_MM) return { error: 'Dinding terlalu pendek untuk pintu (< 700 mm)' }
    lo = Math.round(Math.min(hi0 - width, Math.max(lo0, along(h!, a) - width / 2)))
    hi = lo + width
  } else {
    const [ta, tb] = h ? [along(h, a), along(h, b)].sort((x, y) => x - y) : [0, 0]
    lo = Math.round(Math.max(lo0, ta))
    hi = Math.round(Math.min(hi0, tb))
    if (!h || hi - lo < DOOR_MIN_MM) {
      const [p, q] = [snapEnd(view, a), snapEnd(view, b)]
      const width = Math.floor(Math.hypot(q[0] - p[0], q[1] - p[1])) - 2 * END_MARGIN_MM
      if (width < DOOR_MIN_MM) return { error: 'Garis pintu terlalu pendek (< 700 mm)' }
      return { ops: [{ op: 'add_wall', a: p, b: q, thickness, kind: 'partition', openings: [{ offset: END_MARGIN_MM, width, ...DOOR }] }] }
    }
  }
  const hits = (view.openings ?? []).filter((o) => o.wall_id === h!.id && lo < o.offset + o.width && hi > o.offset)
  if (hits.length === 0) return { ops: [{ op: 'add_opening', wall_id: h!.id, offset: lo, width: hi - lo, ...DOOR }] }
  if (click) return { error: 'Sudah ada bukaan di sini; tarik garis di atasnya untuk memindah atau mengubah lebarnya' }
  if (hits.length > 1 || hits[0].category !== 'door') return { error: 'Garis pintu menimpa jendela atau lebih dari satu bukaan' }
  return { ops: [{ op: 'set_door', id: hits[0].id, offset: lo, width: hi - lo }] }
}

export const DOOR_SKIPPED_TEXT: Record<Exclude<DoorSkipped, null>, string> = {
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
