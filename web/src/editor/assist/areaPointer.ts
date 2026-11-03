import type { PointerEvent } from 'react'
import { ApiError } from '../../api/client'
import { useEditorStore } from '../store'
import { useAssistStore } from './store'
import { drawnBox } from './stream'

type Pt = [number, number]

/** Tool A on a plan canvas (layout review or installation): a drag marks the area, a click points at drawn
 *  equipment (K1, K2, ...), a Shift-drag fits a box to the drawn lines. Returns true: the canvas does nothing else. */
export function areaPointer(projectId: string, kind: 'down' | 'move' | 'up', mm: Pt, e: PointerEvent,
  rough: { a: Pt; b: Pt } | null, setRough: (r: { a: Pt; b: Pt } | null) => void): boolean {
  // "Perbaiki area": drag a box; the chat panel on the right takes the instruction
  if (kind === 'down') setRough({ a: mm, b: mm })
  else if (kind === 'move' && rough) setRough({ ...rough, b: mm })
  else if (kind === 'up' && rough) {
    const [a, b] = [rough.a, mm]
    setRough(null)
    const dragged = Math.abs(b[0] - a[0]) > 300 && Math.abs(b[1] - a[1]) > 300
    if (dragged && !e.shiftKey) {
      useAssistStore.getState().open([Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[0], b[0]), Math.max(a[1], b[1])].map(Math.round) as [number, number, number, number])
    } else if (dragged || Math.hypot(b[0] - a[0], b[1] - a[1]) < 300) {
      // a click points at drawn equipment (K1, K2, ...); Shift-drag fits a box to the drawn lines
      const at = dragged ? { a: a.map(Math.round) as Pt, b: b.map(Math.round) as Pt } : { at: b.map(Math.round) as Pt }
      drawnBox(projectId, at).then((found) => {
        const s = useAssistStore.getState()
        if (!s.box) s.open(boxAround(found.center, found.size))
        s.addDrawn(found)
      }).catch((err) => {
        // a click on empty floor, a wall or a room's own outline: just a selection (the room stays selected)
        if (err instanceof ApiError && (err.code === 'no_box' || err.code === 'is_room')) return
        useEditorStore.getState().setNotice({ kind: 'warning', text: err instanceof Error ? err.message : String(err) })
      })
    }
  }
  return true
}

/** An area around a pointed box when no area was marked yet: the chat needs one. */
function boxAround(c: Pt, size: [number, number]): [number, number, number, number] {
  const r = size[1] / 2 + 1500
  return [c[0] - r, c[1] - r, c[0] + r, c[1] + r].map(Math.round) as [number, number, number, number]
}
