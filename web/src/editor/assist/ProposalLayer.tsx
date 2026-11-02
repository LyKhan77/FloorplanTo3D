import { svgPoint } from '../review/planTransform'
import { useEditorStore } from '../store'
import { useAssistStore } from './store'

type Pt = [number, number]
const RED = '#fa4d56', GREEN = '#42be65', YELLOW = '#f1c21b', PURPLE = '#a56eff'

function Seg({ a, b, color, width = 120, dash }: { a: Pt; b: Pt; color: string; width?: number; dash?: string }) {
  const [p, q] = [svgPoint(a), svgPoint(b)]
  return <line x1={p[0]} y1={p[1]} x2={q[0]} y2={q[1]} stroke={color} strokeWidth={width} strokeDasharray={dash}
    strokeLinecap="square" style={{ pointerEvents: 'none' }} />
}

/** The marked box and the open proposal over the review canvas; nothing here is in the editor store until Terima. */
export function ProposalLayer({ draft }: { draft: [Pt, Pt] | null }) {
  const box = useAssistStore((s) => s.box)
  const p = useAssistStore((s) => s.proposal)
  const view = useEditorStore((s) => s.view)
  const rect = draft ? [Math.min(draft[0][0], draft[1][0]), Math.min(draft[0][1], draft[1][1]),
    Math.max(draft[0][0], draft[1][0]), Math.max(draft[0][1], draft[1][1])] : box
  const walls = new Map((view?.walls ?? []).map((w) => [w.id, w]))
  return (
    <g className="assist-layer">
      {rect && (() => {
        const [x, y] = svgPoint([rect[0], rect[3]])
        return <rect x={x} y={y} width={rect[2] - rect[0]} height={rect[3] - rect[1]} fill="rgba(165,110,255,0.07)"
          stroke={PURPLE} strokeWidth={50} strokeDasharray="300 180" style={{ pointerEvents: 'none' }} />
      })()}
      {p?.deleted.map((id) => {
        const w = walls.get(id)
        if (w) return <Seg key={id} a={w.a as Pt} b={w.b as Pt} color={RED} dash="300 180" />
        const o = view?.openings?.find((x) => x.id === id), host = o && walls.get(o.wall_id)
        if (!o || !host) return null
        const len = Math.hypot(host.b[0] - host.a[0], host.b[1] - host.a[1])
        const at = (d: number): Pt => [host.a[0] + ((host.b[0] - host.a[0]) * d) / len, host.a[1] + ((host.b[1] - host.a[1]) * d) / len]
        return <Seg key={id} a={at(o.offset)} b={at(o.offset + o.width)} color={RED} width={220} dash="120 80" />
      })}
      {p?.moved.map((m) => <Seg key={m.id} a={m.a} b={m.b} color={GREEN} />)}
      {p?.added.map((w, i) => <Seg key={i} a={w.a} b={w.b} color={w.snapped ? GREEN : YELLOW} width={Math.max(w.thickness, 100)} />)}
      {p?.openings.map((o, i) => <Seg key={i} a={o.a} b={o.b} color={o.snapped ? GREEN : YELLOW} width={260} />)}
    </g>
  )
}
