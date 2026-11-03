import { useEffect, useRef, useState } from 'react'
import { useTemplates } from '../api/hooks'
import type { Backdrop } from '../api/types'
import { ignoredTarget } from '../editor/lib/keys'
import { ReviewCanvas } from '../editor/review/ReviewCanvas'
import { svgPoint } from '../editor/review/planTransform'
import { useEditorStore } from '../editor/store'
import { ApiError } from '../api/client'
import { fitBox, snapBox, snapTray, type Drop, type SnapBox } from './api'
import { InstallLayer } from './InstallLayer'
import { cleanPath, DEFAULT_WIDTH, TRAY_COLOUR, type InstallOp } from './reducer'
import { MOVE_REASON, TURN_REASON } from './deviceOps'
import { useInstallStore, type InstallTool } from './store'
import { areaPointer } from '../editor/assist/areaPointer'
import { ProposalLayer } from '../editor/assist/ProposalLayer'
import { useAssistStore } from '../editor/assist/store'

type Pt = [number, number]
const SAME_RACK_MM = 100  // a traced box whose centre is this close to a placed rack is that rack again

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

  // a rack already placed here (in the installation, or a rack object of the layout) is not traced twice
  const taken = (c: Pt, more: Pt[] = []) => [
    ...(useInstallStore.getState().view?.objects ?? []).map((o) => [o.position[0], o.position[1]] as Pt),
    ...(layout?.objects ?? []).filter((o) => templates.find((t) => t.id === o.template_id)?.category === 'rack').map((o) => [o.position[0], o.position[1]] as Pt),
    ...more,
  ].some((p) => Math.hypot(p[0] - c[0], p[1] - c[1]) < SAME_RACK_MM)

  const placeRack = async (at: Pt) => {
    const s = useInstallStore.getState()
    let r: SnapBox
    try {
      r = await snapBox(projectId, at)
    } catch {
      s.setNotice({ kind: 'warning', text: 'Tidak ada kotak rack di sini' })
      return
    }
    if (taken(r.center)) { s.setNotice({ kind: 'info', text: 'Rack sudah ada di sini' }); return }
    const op = rackOp(r)
    if (op) s.apply(op)
    else s.setNotice({ kind: 'warning', text: 'Tidak ada template rack di registry' })
  }

  // Shift-drag: one rack exactly where it was dragged, each side moved onto a drawn line nearby (any cabinet drawing:
  // outlined, filled, hatched, with text); without an extraction run to fit to, the dragged box itself
  const placeRackOn = async (a: Pt, b: Pt) => {
    const s = useInstallStore.getState()
    let r: SnapBox
    try {
      r = await fitBox(projectId, a, b)
    } catch (e) {
      const w = Math.abs(b[0] - a[0]), d = Math.abs(b[1] - a[1])
      if (!(e instanceof ApiError && e.code === 'no_run') || Math.min(w, d) < 300 || Math.max(w, d) > 3000) {
        s.setNotice({ kind: 'warning', text: 'Tarik kotak seukuran rack: 300–3000 mm per sisi' })
        return
      }
      r = { center: [Math.round((a[0] + b[0]) / 2), Math.round((a[1] + b[1]) / 2)], size: [Math.min(w, d), Math.max(w, d)] as Pt,
        rotation: d >= w ? 0 : 90, template_id: null }
    }
    if (taken(r.center)) { s.setNotice({ kind: 'info', text: 'Rack sudah ada di sini' }); return }
    const op = rackOp(r)
    if (op) s.apply(op)
    else s.setNotice({ kind: 'warning', text: 'Tidak ada template rack di registry' })
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

  const [rough, setRough] = useState<{ a: Pt; b: Pt } | null>(null)
  // tool A here fills rooms with equipment (the installation layer of the area assistant)
  useEffect(() => {
    if (tool === 'assist') useAssistStore.getState().setLayer('installation')
    else if (useAssistStore.getState().layer === 'installation') useAssistStore.getState().close()
  }, [tool])
  // leaving the installation canvas ends an equipment chat: its Terima must never land in the layout's mode
  useEffect(() => () => { if (useAssistStore.getState().layer === 'installation') useAssistStore.getState().setLayer('layout') }, [])
  // select tool: dragging a selected device moves it
  const [moving, setMoving] = useState<{ id: string; from: Pt; to: Pt } | null>(null)
  const onPointer = (kind: 'down' | 'move' | 'up', mm: Pt, e: React.PointerEvent) => {
    if (e.button > 0) return false
    if (tool === 'select') return moveDevice(kind, mm)
    if (tool === 'assist') return areaPointer(projectId, kind, mm, e, rough, setRough)
    const p: Pt = [Math.round(mm[0]), Math.round(mm[1])]
    if (tool === 'rack' && e.shiftKey) {
      if (kind === 'down') setBox({ a: p, b: p })
      else if (kind === 'move' && box) setBox({ ...box, b: p })
      else if (kind === 'up' && box) { setBox(null); void placeRackOn(box.a, p) }
      return true
    }
    if (kind !== 'up') return true
    if (tool === 'tray') useInstallStore.getState().setTrayDraft([...useInstallStore.getState().trayDraft, p])
    else void placeRack(p)
    return true
  }

  const moveDevice = (kind: 'down' | 'move' | 'up', mm: Pt): boolean => {
    const s = useInstallStore.getState()
    if (kind === 'down') {
      const hit = (s.view?.objects ?? []).find((o) => s.selection.includes(o.id) && inside(o, mm))
      if (!hit) return false
      setMoving({ id: hit.id, from: mm, to: mm })
      return true
    }
    if (!moving) return false
    if (kind === 'move') { setMoving({ ...moving, to: mm }); return true }
    const [dx, dy] = [mm[0] - moving.from[0], mm[1] - moving.from[1]]
    setMoving(null)
    const o = s.view?.objects?.find((x) => x.id === moving.id)
    if (o && Math.hypot(dx, dy) >= MOVE_MIN_MM) {
      s.apply({ op: 'update_object', id: o.id, position: [Math.round(o.position[0] + dx), Math.round(o.position[1] + dy), o.position[2]],
        reason: MOVE_REASON })
    }
    return true
  }

  // a Library card dropped on the canvas: the device stands there, facing north (R turns it, Properties sets Z)
  const zoneRef = useRef<HTMLDivElement>(null)
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const ed = useEditorStore.getState()
    const key = e.dataTransfer?.getData('application/x-template') || ''
    const t = ed.dragging ?? templates.find((x) => `${x.id}@${x.version}` === key)
    ed.setDragging(null)
    if (!t) return
    const svg = zoneRef.current?.querySelector('svg'), m = svg?.getScreenCTM?.()
    let p: Pt = [e.clientX, -e.clientY]  // no layout (jsdom): client px are SVG units
    if (svg && m) {
      const q = Object.assign(svg.createSVGPoint(), { x: e.clientX, y: e.clientY }).matrixTransform(m.inverse())
      p = [q.x, -q.y]
    }
    if (!p.every(Number.isFinite)) return
    useInstallStore.getState().apply({ op: 'add_object', template_id: t.id, template_version: t.version,
      position: [Math.round(p[0]), Math.round(p[1]), 0], rotation: 0, dims: [t.dims.w, t.dims.d, t.dims.h] })
  }

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (ignoredTarget(e.target as Element | null) || e.ctrlKey || e.metaKey || e.altKey) return
      const s = useInstallStore.getState()
      if (e.key === 'Enter' && s.tool === 'tray') { void finishTray(); return }
      if (e.key === 'Escape') { s.setTrayDraft([]); s.setTool('select'); setBox(null); setRough(null); return }
      const t = ({ v: 'select', t: 'tray', k: 'rack', a: 'assist' } as Record<string, InstallTool>)[e.key.toLowerCase()]
      if (t) s.setTool(t)
      if (e.key.toLowerCase() === 'r' && s.tool === 'select' && s.selection.length === 1) {
        const o = s.view?.objects?.find((x) => x.id === s.selection[0])
        if (o) s.apply({ op: 'update_object', id: o.id, rotation: ((o.rotation ?? 0) + 90) % 360, reason: TURN_REASON })
      }
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
        {tool === 'rack' && <span className="helper">Klik di dalam kotak rack · Shift-tarik: gambar rack sendiri</span>}
      </div>
      <div ref={zoneRef} data-drop-zone className="install-drop-zone" onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
      <ReviewCanvas rooms={layout?.rooms ?? []} tasks={[]} backdrop={backdrop} onCanvasPointer={onPointer} readOnly>
        <InstallLayer drops={drops} />
        {tool === 'assist' && <ProposalLayer draft={rough ? [rough.a, rough.b] : null} />}
        {box && (() => {
          const [a, b] = [svgPoint(box.a), svgPoint(box.b)]
          return <rect x={Math.min(a[0], b[0])} y={Math.min(a[1], b[1])} width={Math.abs(b[0] - a[0])} height={Math.abs(b[1] - a[1])}
            fill="rgba(165,110,255,.12)" stroke="#a56eff" strokeWidth={40} />
        })()}
        {moving && (() => {
          const [a, b] = [svgPoint(moving.from), svgPoint(moving.to)]
          return <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#ffffff" strokeWidth={40} strokeDasharray="160 100" />
        })()}
      </ReviewCanvas>
      </div>
    </>
  )
}

const MOVE_MIN_MM = 20  // a smaller drag is a click

/** Is the point inside the device's footprint (rotated CCW about its centre)? */
function inside(o: { position: number[]; rotation?: number | null; dims: number[] }, p: Pt): boolean {
  const t = (-(o.rotation ?? 0) * Math.PI) / 180, dx = p[0] - o.position[0], dy = p[1] - o.position[1]
  const lx = dx * Math.cos(t) - dy * Math.sin(t), ly = dx * Math.sin(t) + dy * Math.cos(t)
  return Math.abs(lx) <= o.dims[0] / 2 && Math.abs(ly) <= o.dims[1] / 2
}

const TOOLS: [InstallTool, string, string][] = [['select', 'Pilih', 'V'], ['tray', 'Tray', 'T'], ['rack', 'Rack', 'K'],
  ['assist', 'Isi ruang', 'A']]
