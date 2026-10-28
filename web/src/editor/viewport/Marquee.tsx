import { useEffect, useState, type RefObject } from 'react'
import { Vector3, type Camera } from 'three'
import { toThree } from '../lib/coords'
import { idsInRect } from '../lib/rectPick'
import { useEditorStore } from '../store'
import { gizmoState } from './gizmoState'

type Rect = { x0: number; y0: number; x1: number; y1: number }

/** Top mode + select tool: left-drag on the canvas selects walls fully inside the box and objects whose position falls in it (Shift adds). */
export function Marquee({ wrap, camera }: { wrap: RefObject<HTMLDivElement | null>; camera: { current: Camera | null } }) {
  const [rect, setRect] = useState<Rect | null>(null)
  useEffect(() => {
    const el = wrap.current
    if (!el) return
    let start: Rect | null = null
    const local = (e: PointerEvent) => {
      const r = el.getBoundingClientRect()
      return [e.clientX - r.left, e.clientY - r.top]
    }
    const down = (e: PointerEvent) => {
      const s = useEditorStore.getState()
      if (e.button !== 0 || s.mode !== 'top' || s.tool !== 'select' || gizmoState.dragging) return
      const [x, y] = local(e)
      start = { x0: x, y0: y, x1: x, y1: y }
    }
    const move = (e: PointerEvent) => {
      if (!start) return
      const [x, y] = local(e)
      start = { ...start, x1: x, y1: y }
      if (Math.hypot(x - start.x0, y - start.y0) > 4) setRect(start)
    }
    const up = (e: PointerEvent) => {
      const r = start
      start = null
      setRect(null)
      if (!r || Math.hypot(r.x1 - r.x0, r.y1 - r.y0) <= 4 || !camera.current || gizmoState.dragging) return
      const { width, height } = el.getBoundingClientRect()
      const [xa, xb] = [Math.min(r.x0, r.x1), Math.max(r.x0, r.x1)], [ya, yb] = [Math.min(r.y0, r.y1), Math.max(r.y0, r.y1)]
      const s = useEditorStore.getState()
      const ids = s.view ? idsInRect(s.view, { xa, xb, ya, yb }, (q) => {
        const p = new Vector3(...toThree(q)).project(camera.current!)
        return [((p.x + 1) / 2) * width, ((1 - p.y) / 2) * height]
      }) : []
      const additive = e.shiftKey
      // after the click that ends this drag, which would otherwise select the floor under the cursor
      setTimeout(() => useEditorStore.getState().select(ids, additive), 0)
    }
    el.addEventListener('pointerdown', down)
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    return () => {
      el.removeEventListener('pointerdown', down)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
  }, [wrap, camera])
  if (!rect) return null
  return (
    <div className="editor-marquee" style={{ left: Math.min(rect.x0, rect.x1), top: Math.min(rect.y0, rect.y1),
      width: Math.abs(rect.x1 - rect.x0), height: Math.abs(rect.y1 - rect.y0) }} />
  )
}
