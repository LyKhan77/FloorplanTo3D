import { useEffect, useState } from 'react'
import { useTemplates } from '../api/hooks'
import type { Backdrop } from '../api/types'
import { ignoredTarget } from '../editor/lib/keys'
import { ReviewCanvas } from '../editor/review/ReviewCanvas'
import { svgPoint } from '../editor/review/planTransform'
import { useEditorStore } from '../editor/store'
import { snapBox, snapTray, type Drop, type SnapBox } from './api'
import { InstallLayer } from './InstallLayer'
import { cleanPath, DEFAULT_WIDTH, TRAY_COLOUR, type InstallOp } from './reducer'
import { useInstallStore, type InstallTool } from './store'

type Pt = [number, number]
const GRID_MM = 600  // a Shift-drag box looks for racks on this grid inside it

/** Mode Instalasi (M12a): the layout read-only over the plan, with the tray tool (T) and the rack tool (K). */
export function InstallWorkspace({ projectId, backdrop, drops }: { projectId: string; backdrop: Backdrop | null; drops: Drop[] }) {
  const layout = useEditorStore((s) => s.view)
  const tool = useInstallStore((s) => s.tool)
  const trayClass = useInstallStore((s) => s.trayClass)
  const { data: templates = [] } = useTemplates()
  const [box, setBox] = useState<{ a: Pt; b: Pt } | null>(null)

  const rackOp = (r: SnapBox): InstallOp | null => {
    const t = r.template_id ? null : templates.find((x) => x.category === 'rack')
    const id = r.template_id ?? t?.id, version = r.template_version ?? t?.version
    if (!id || !version) return null
    const dims: [number, number, number] = r.dims ?? [r.size[0], r.size[1], t?.dims.h ?? 2000]
    return { op: 'add_object', template_id: id, template_version: version, position: [r.center[0], r.center[1], 0], rotation: r.rotation, dims,
      evidence: { box: r.size } }
  }

  const placeRack = async (at: Pt) => {
    const s = useInstallStore.getState()
    try {
      const op = rackOp(await snapBox(projectId, at))
      if (op) s.apply(op)
      else s.setNotice({ kind: 'warning', text: 'Tidak ada template rack di registry' })
    } catch {
      s.setNotice({ kind: 'warning', text: 'Tidak ada kotak rack di sini' })
    }
  }

  const placeRacksIn = async (a: Pt, b: Pt) => {
    const [x0, x1] = [Math.min(a[0], b[0]), Math.max(a[0], b[0])], [y0, y1] = [Math.min(a[1], b[1]), Math.max(a[1], b[1])]
    const found: SnapBox[] = []
    for (let x = x0 + GRID_MM / 2; x < x1; x += GRID_MM) {
      for (let y = y0 + GRID_MM / 2; y < y1; y += GRID_MM) {
        const r = await snapBox(projectId, [x, y]).catch(() => null)
        if (r && !found.some((f) => Math.hypot(f.center[0] - r.center[0], f.center[1] - r.center[1]) < 100)) found.push(r)
      }
    }
    const ops = found.map(rackOp).filter((o): o is InstallOp => o !== null)
    const s = useInstallStore.getState()
    if (ops.length) s.applyMany(ops)
    else s.setNotice({ kind: 'warning', text: 'Tidak ada kotak rack di area ini' })
  }

  const finishTray = async () => {
    const s = useInstallStore.getState()
    const drawn = cleanPath(s.trayDraft)
    s.setTrayDraft([])
    if (drawn.length < 2) return
    let path = drawn, width: number = DEFAULT_WIDTH[s.trayClass]
    try {
      const r = await snapTray(projectId, drawn)
      path = r.path
      width = r.width
    } catch {
      s.setNotice({ kind: 'info', text: 'Tidak ada pita tray di dekat garis ini: jalur dipakai seperti digambar' })
    }
    useInstallStore.getState().apply({ op: 'add_tray', path, tray_class: s.trayClass, width })
  }

  const onPointer = (kind: 'down' | 'move' | 'up', mm: Pt, e: React.PointerEvent) => {
    if (e.button > 0 || tool === 'select') return false
    const p: Pt = [Math.round(mm[0]), Math.round(mm[1])]
    if (tool === 'rack' && e.shiftKey) {
      if (kind === 'down') setBox({ a: p, b: p })
      else if (kind === 'move' && box) setBox({ ...box, b: p })
      else if (kind === 'up' && box) { setBox(null); void placeRacksIn(box.a, p) }
      return true
    }
    if (kind !== 'up') return true
    if (tool === 'tray') useInstallStore.getState().setTrayDraft([...useInstallStore.getState().trayDraft, p])
    else void placeRack(p)
    return true
  }

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (ignoredTarget(e.target as Element | null) || e.ctrlKey || e.metaKey || e.altKey) return
      const s = useInstallStore.getState()
      if (e.key === 'Enter' && s.tool === 'tray') { void finishTray(); return }
      if (e.key === 'Escape') { s.setTrayDraft([]); s.setTool('select'); setBox(null); return }
      const t = ({ v: 'select', t: 'tray', k: 'rack' } as Record<string, InstallTool>)[e.key.toLowerCase()]
      if (t) s.setTool(t)
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  })

  return (
    <>
      <div className="review-tools" role="toolbar" aria-label="Alat instalasi">
        {TOOLS.map(([t, label, k]) => (
          <button key={t} type="button" aria-label={label} aria-pressed={tool === t} className={tool === t ? 'is-on' : undefined}
            onClick={() => useInstallStore.getState().setTool(t)}>{label} <kbd>{k}</kbd></button>
        ))}
        {(['data', 'power'] as const).map((c) => (
          <button key={c} type="button" aria-pressed={trayClass === c} className={trayClass === c ? 'is-on' : undefined}
            style={{ borderColor: TRAY_COLOUR[c] }} onClick={() => useInstallStore.getState().setTrayClass(c)}>{c === 'data' ? 'Data' : 'Power'}</button>
        ))}
        {tool === 'tray' && <span className="helper">Klik titik-titik jalur · Enter selesai · Esc batal</span>}
        {tool === 'rack' && <span className="helper">Klik di dalam kotak rack · Shift-tarik untuk sederet rack</span>}
      </div>
      <ReviewCanvas rooms={layout?.rooms ?? []} tasks={[]} backdrop={backdrop} onCanvasPointer={onPointer} readOnly>
        <InstallLayer drops={drops} />
        {box && (() => {
          const [a, b] = [svgPoint(box.a), svgPoint(box.b)]
          return <rect x={Math.min(a[0], b[0])} y={Math.min(a[1], b[1])} width={Math.abs(b[0] - a[0])} height={Math.abs(b[1] - a[1])}
            fill="rgba(165,110,255,.12)" stroke="#a56eff" strokeWidth={40} />
        })()}
      </ReviewCanvas>
    </>
  )
}

const TOOLS: [InstallTool, string, string][] = [['select', 'Pilih', 'V'], ['tray', 'Tray', 'T'], ['rack', 'Rack', 'K']]
