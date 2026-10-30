import { svgPoint } from '../editor/review/planTransform'
import type { CableTray, PlacedObject } from '../types/installation'
import type { Drop } from './api'
import { TRAY_COLOUR } from './reducer'
import { useInstallStore } from './store'

type Pt = [number, number]

const pts = (path: Pt[]) => path.map((p) => svgPoint(p).join(',')).join(' ')

function corners(o: PlacedObject): Pt[] {
  const [x, y] = o.position, [w, d] = o.dims, r = ((o.rotation ?? 0) * Math.PI) / 180
  const c = Math.cos(r), s = Math.sin(r)
  return ([[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]] as Pt[]).map(([u, v]) => [x + u * c - v * s, y + u * s + v * c])
}

/** Trays, racks and drops over the read-only layout (M12a). Trays at their real width; drops dashed from tray to rack. */
export function InstallLayer({ drops }: { drops: Drop[] }) {
  const view = useInstallStore((s) => s.view)
  const selection = useInstallStore((s) => s.selection)
  const draft = useInstallStore((s) => s.trayDraft)
  const trayClass = useInstallStore((s) => s.trayClass)
  const tool = useInstallStore((s) => s.tool)
  const pick = (id: string) => (e: React.MouseEvent) => {
    if (tool !== 'select') return
    e.stopPropagation()
    useInstallStore.getState().select([id])
  }
  const sel = new Set(selection)
  return (
    <g className="install-layer">
      {(view?.cable_trays ?? []).map((t: CableTray) => (
        <polyline key={t.id} data-tray={t.id} points={pts(t.path as Pt[])} fill="none" stroke={sel.has(t.id) ? '#ffffff' : TRAY_COLOUR[t.tray_class]}
          strokeOpacity={sel.has(t.id) ? 0.8 : 0.45} strokeWidth={t.width ?? 200} strokeLinejoin="miter" strokeLinecap="butt"
          onClick={pick(t.id)} style={{ cursor: tool === 'select' ? 'pointer' : undefined }} />
      ))}
      {(view?.objects ?? []).map((o) => {
        const [x, y] = svgPoint([o.position[0], o.position[1]])
        return (
          <g key={o.id} data-rack={o.id} onClick={pick(o.id)} style={{ cursor: tool === 'select' ? 'pointer' : undefined }}>
            <polygon points={pts(corners(o))} fill="#8a3ffc" fillOpacity={0.25} stroke={sel.has(o.id) ? '#ffffff' : '#a56eff'} strokeWidth={40} />
            <text x={x} y={y} fill="#f4f4f4" fontSize={220} textAnchor="middle" dominantBaseline="middle" style={{ pointerEvents: 'none' }}>{o.label || o.id}</text>
          </g>
        )
      })}
      {drops.map((d) => {
        const [a, b] = [svgPoint(d.at), svgPoint(d.to)]
        return <line key={`${d.rack_id}-${d.tray_id}`} data-drop={d.rack_id} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]}
          stroke={TRAY_COLOUR[d.tray_class]} strokeWidth={60} strokeDasharray="160 100" style={{ pointerEvents: 'none' }} />
      })}
      {draft.length > 0 && (
        <polyline points={pts(draft)} fill="none" stroke={TRAY_COLOUR[trayClass]} strokeWidth={80} strokeDasharray="200 120" style={{ pointerEvents: 'none' }} />
      )}
    </g>
  )
}
