import { useEffect, useMemo, useRef, useState, type PointerEvent as RPointerEvent, type ReactNode } from 'react'
import type { Backdrop, ReviewTask } from '../../api/types'
import type { Room } from '../../types/spec'
import { idsInRect } from '../lib/rectPick'
import { useEditorStore } from '../store'
import { imageMatrix, svgPoint } from './planTransform'

const PAD_MM = 2000
const DOOR = '#ff832b', WINDOW = '#33b1ff'  // bright on the dark canvas: a black door read as an open gap
const ROOM_FILLS = ['#4589ff', '#08bdba', '#a56eff', '#42be65', '#ff7eb6', '#d2a106', '#33b1ff']
type Box = [number, number, number, number]  // x, y, w, h in SVG units (mm, y flipped)

function useImageSize(url: string | undefined) {
  const [size, setSize] = useState<[number, number] | null>(null)
  useEffect(() => {
    if (!url) return
    const img = new Image()
    img.onload = () => setSize([img.naturalWidth, img.naturalHeight])
    img.src = url
  }, [url])
  return size
}

const pts = (ring: number[][]) => ring.map((p) => svgPoint(p).join(',')).join(' ')

/** M8 review canvas: the spec in 2D over the page it was read from (works before any 3D shell exists). */
export function ReviewCanvas({ rooms, tasks, backdrop, showImage = true, children, onCanvasPointer }: {
  rooms: Room[]; tasks: ReviewTask[]; backdrop: Backdrop | null; showImage?: boolean; children?: ReactNode
  /** tools (Task 5) take the pointer first; returning true stops the default select/marquee/pan */
  onCanvasPointer?: (kind: 'down' | 'move' | 'up', mm: [number, number], e: RPointerEvent) => boolean
}) {
  const view = useEditorStore((s) => s.view)
  const selection = useEditorStore((s) => s.selection)
  const svgRef = useRef<SVGSVGElement>(null)
  const dragged = useRef(false)
  const imgSize = useImageSize(backdrop?.url)
  const home = useMemo<Box>(() => {
    const xs = (view?.walls ?? []).flatMap((w) => [w.a[0], w.b[0]]), ys = (view?.walls ?? []).flatMap((w) => [w.a[1], w.b[1]])
    if (!xs.length) return [0, -10000, 10000, 10000]
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
    return [x0 - PAD_MM, -y1 - PAD_MM, x1 - x0 + 2 * PAD_MM, y1 - y0 + 2 * PAD_MM]
  }, [view])
  const [box, setBox] = useState<Box | null>(null)
  const vb = box ?? home
  const [drag, setDrag] = useState<{ kind: 'pan' | 'marquee'; a: [number, number]; b: [number, number] } | null>(null)
  // a task picked in the list (or any setFocus) recentres the canvas, keeping a readable 12 m wide window
  const focus = useEditorStore((s) => s.focus)
  const [seenFocus, setSeenFocus] = useState(focus)
  if (focus && focus !== seenFocus) {  // derived state: recentre once per setFocus call
    setSeenFocus(focus)
    const [x, y] = svgPoint(focus)
    setBox([x - 6000, y - 4000, 12000, 8000])
  }
  const leak = useMemo(() => new Set(tasks.filter((t) => t.kind === 'leak').flatMap((t) => t.element_ids)), [tasks])
  const sel = useMemo(() => new Set(selection), [selection])

  const toSvg = (e: { clientX: number; clientY: number }): [number, number] => {
    const svg = svgRef.current, m = svg?.getScreenCTM?.()
    if (!svg || !m) return [e.clientX, e.clientY]  // no layout (jsdom): client px are SVG units
    const p = svg.createSVGPoint()
    p.x = e.clientX
    p.y = e.clientY
    const q = p.matrixTransform(m.inverse())
    return [q.x, q.y]
  }
  const mm = (s: [number, number]): [number, number] => [s[0], -s[1]]

  const onWheel = (e: React.WheelEvent) => {
    const [cx, cy] = toSvg(e), k = e.deltaY > 0 ? 1.15 : 1 / 1.15
    setBox([cx - (cx - vb[0]) * k, cy - (cy - vb[1]) * k, vb[2] * k, vb[3] * k])
  }
  const down = (e: RPointerEvent<SVGSVGElement>) => {
    const s = toSvg(e)
    if (onCanvasPointer?.('down', mm(s), e)) return
    if (e.button === 1 || e.altKey) setDrag({ kind: 'pan', a: s, b: s })
    // rooms fill the whole interior: a marquee starts on them too (a click without a drag still picks the room)
    else if (e.button === 0 && (e.target === e.currentTarget || (e.target as Element).hasAttribute?.('data-room'))) setDrag({ kind: 'marquee', a: s, b: s })
  }
  const move = (e: RPointerEvent<SVGSVGElement>) => {
    const s = toSvg(e)
    if (onCanvasPointer?.('move', mm(s), e)) return
    if (!drag) return
    if (drag.kind === 'pan') setBox([vb[0] - (s[0] - drag.a[0]), vb[1] - (s[1] - drag.a[1]), vb[2], vb[3]])
    else setDrag({ ...drag, b: s })
  }
  const up = (e: RPointerEvent<SVGSVGElement>) => {
    const s = toSvg(e)
    const d = drag
    setDrag(null)
    if (onCanvasPointer?.('up', mm(s), e)) return
    if (d?.kind !== 'marquee' || !view) return
    const [xa, xb] = [Math.min(d.a[0], d.b[0]), Math.max(d.a[0], d.b[0])], [ya, yb] = [Math.min(d.a[1], d.b[1]), Math.max(d.a[1], d.b[1])]
    if (xb - xa < 50 && yb - ya < 50) { if (!e.shiftKey) useEditorStore.getState().select([]); return }
    dragged.current = true  // the click that ends this drag must not pick the room under the cursor
    setTimeout(() => { dragged.current = false }, 0)
    useEditorStore.getState().select(idsInRect(view, { xa, xb, ya, yb }, (p) => svgPoint(p)), e.shiftKey)
  }
  const pick = (id: string) => (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!dragged.current) useEditorStore.getState().select([id], e.shiftKey)
  }

  if (!view) return null
  const walls = new Map((view.walls ?? []).map((w) => [w.id, w]))
  return (
    <svg ref={svgRef} className="review-canvas" viewBox={vb.join(' ')} role="application" aria-label="Kanvas review"
      onWheel={onWheel} onPointerDown={down} onPointerMove={move} onPointerUp={up} style={{ background: '#0b0b0b', touchAction: 'none' }}>
      {backdrop && showImage && imgSize && (
        <image href={backdrop.url} width={imgSize[0]} height={imgSize[1]} transform={imageMatrix(backdrop.px_to_mm)} opacity={0.5}
          style={{ pointerEvents: 'none', filter: 'invert(1)' }} />
      )}
      {backdrop && showImage && !imgSize && <image href={backdrop.url} transform={imageMatrix(backdrop.px_to_mm)} opacity={0} />}
      {rooms.map((r, i) => (
        <polygon key={r.id} data-room={r.id} points={pts(r.polygon as number[][])} className={leak.has(r.id) ? 'is-leak' : undefined}
          fill={leak.has(r.id) ? '#fa4d56' : ROOM_FILLS[i % ROOM_FILLS.length]} fillOpacity={leak.has(r.id) ? 0.28 : sel.has(r.id) ? 0.3 : 0.1}
          stroke={sel.has(r.id) ? '#ffffff' : 'none'} strokeWidth={60} onClick={pick(r.id)} style={{ cursor: 'pointer' }} />
      ))}
      {(view.stairs ?? []).map((st) => (
        <g key={st.id}>
          {(st.landings ?? []).map((l, i) => <polygon key={i} points={pts(l as number[][])} fill="#d2a106" fillOpacity={0.15} style={{ pointerEvents: 'none' }} />)}
          {st.flights.map((f, i) => {
            const [a, b] = [svgPoint(f.start as number[]), svgPoint(f.end as number[])]
            const tread = Math.hypot(b[0] - a[0], b[1] - a[1]) / Math.max(1, f.risers)
            return (
              <g key={i}>
                <line data-stair={st.id} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} strokeWidth={f.width} stroke="#d2a106"
                  strokeOpacity={sel.has(st.id) ? 0.5 : 0.22} onClick={pick(st.id)} style={{ cursor: 'pointer' }} />
                {/* one stripe per riser, so a flight reads as steps */}
                <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} strokeWidth={f.width} stroke="#d2a106" strokeOpacity={0.6}
                  strokeDasharray={`30 ${Math.max(1, tread - 30)}`} style={{ pointerEvents: 'none' }} />
              </g>
            )
          })}
        </g>
      ))}
      {(view.columns ?? []).map((c) => {
        const [x, y] = svgPoint(c.center as number[]), [w, h] = c.size as number[]
        return c.shape === 'circle'
          ? <circle key={c.id} data-column={c.id} cx={x} cy={y} r={w / 2} fill="#8d8d8d" style={{ pointerEvents: 'none' }} />
          : <rect key={c.id} data-column={c.id} x={x - w / 2} y={y - h / 2} width={w} height={h} fill="#8d8d8d"
              transform={`rotate(${-(c.rotation ?? 0)} ${x} ${y})`} style={{ pointerEvents: 'none' }} />
      })}
      {(view.walls ?? []).map((w) => {
        const [a, b] = [svgPoint(w.a), svgPoint(w.b)]
        return <line key={w.id} data-wall={w.id} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} strokeWidth={Math.max(w.thickness, 60)}
          stroke={sel.has(w.id) ? '#ffffff' : w.provenance?.source === 'editor' ? '#42be65' : '#4589ff'} strokeLinecap="square"
          onClick={pick(w.id)} style={{ cursor: 'pointer' }} />
      })}
      {(view.openings ?? []).map((o) => {
        const w = walls.get(o.wall_id)
        if (!w) return null
        const len = Math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1]) || 1, ux = (w.b[0] - w.a[0]) / len, uy = (w.b[1] - w.a[1]) / len
        const a = svgPoint([w.a[0] + ux * o.offset, w.a[1] + uy * o.offset])
        const b = svgPoint([w.a[0] + ux * (o.offset + o.width), w.a[1] + uy * (o.offset + o.width)])
        return <line key={o.id} data-opening={o.id} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} strokeWidth={Math.max(w.thickness, 60) + 20}
          stroke={sel.has(o.id) ? '#ffffff' : o.category === 'door' ? DOOR : WINDOW} onClick={pick(o.id)} style={{ cursor: 'pointer' }} />
      })}
      {rooms.filter((r) => r.name && r.label_pos).map((r) => {
        const [x, y] = svgPoint(r.label_pos!)
        return <text key={`t${r.id}`} x={x} y={y} fill="#f4f4f4" fontSize={350} textAnchor="middle" style={{ pointerEvents: 'none' }}>{r.name}</text>
      })}
      {tasks.map((t) => {
        const [x, y] = svgPoint(t.at)
        return <circle key={t.id} data-task={t.id} cx={x} cy={y} r={220} fill="none" stroke={t.kind === 'leak' ? '#fa4d56' : '#f1c21b'}
          strokeWidth={60} style={{ pointerEvents: 'none' }} />
      })}
      {drag?.kind === 'marquee' && (
        <rect x={Math.min(drag.a[0], drag.b[0])} y={Math.min(drag.a[1], drag.b[1])} width={Math.abs(drag.b[0] - drag.a[0])}
          height={Math.abs(drag.b[1] - drag.a[1])} fill="rgba(69,137,255,.12)" stroke="#4589ff" strokeWidth={40} />
      )}
      {children}
    </svg>
  )
}
