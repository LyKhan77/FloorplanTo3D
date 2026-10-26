import { Html, Line } from '@react-three/drei'
import { useThree } from '@react-three/fiber'
import { useEffect, useRef, useState } from 'react'
import { Mesh, Plane, Raycaster, Vector2, Vector3, type Intersection, type Object3D } from 'three'
import { fromThree, toThree } from '../lib/coords'
import { roomAt } from '../lib/geom'
import { distance, formatM, formatM2, gridIntersections, lockAxis, nearestSnap, shoelaceM2 } from '../lib/measure'
import { snapCandidates } from '../lib/snapCandidates'
import { useEditorStore, type Measurement, type Point3 } from '../store'
import { specIdOf, specTypeOf } from './shellIndex'

const TOOLS = new Set(['distance', 'room-area', 'area', 'height'])
const COLOR = '#f1c21b'
const floor = new Plane(new Vector3(0, 1, 0), 0)
let seq = 0

const shown = (o: Object3D | null): boolean => !o || (o.visible && shown(o.parent))
const lift = (p: Point3, dz = 10): [number, number, number] => toThree([p[0], p[1], p[2] + dz])

function label(m: Measurement, at: Point3) {
  return <Html position={lift(at, 60)} center className="editor-measure-label">{m.label}</Html>
}

function Shape({ m }: { m: Measurement }) {
  const pts = m.points
  if (m.kind === 'distance') {
    const mid: Point3 = [(pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2, (pts[0][2] + pts[1][2]) / 2]
    return <><Line points={pts.map((p) => lift(p, 0))} color={COLOR} lineWidth={2} depthTest={false} />{label(m, mid)}</>
  }
  if (m.kind === 'height') {
    const [x, y, z] = pts[0]
    return <><Line points={[lift([x, y, 0], 0), lift([x, y, z], 0)]} color={COLOR} lineWidth={2} depthTest={false} />{label(m, pts[0])}</>
  }
  const c: Point3 = [pts.reduce((s, p) => s + p[0], 0) / pts.length, pts.reduce((s, p) => s + p[1], 0) / pts.length, 0]
  return <><Line points={[...pts, pts[0]].map((p) => lift(p))} color={COLOR} lineWidth={2} depthTest={false} />{label(m, c)}</>
}

/** Measure tools (07 §5): clicks on the canvas, snapping to candidates within 10 px. Mounted with key={tool}. */
export function MeasureLayer() {
  const { gl, camera, scene } = useThree()
  const tool = useEditorStore((s) => s.tool)
  const measurements = useEditorStore((s) => s.measurements)
  const [pending, setPending] = useState<Point3[]>([])
  const pendingRef = useRef<Point3[]>([])

  useEffect(() => {
    if (!TOOLS.has(tool)) return
    const el = gl.domElement
    const ray = new Raycaster()
    let downAt: [number, number] | null = null
    const set = (pts: Point3[]) => { pendingRef.current = pts; setPending(pts) }
    const cast = (e: MouseEvent) => {
      const r = el.getBoundingClientRect()
      ray.setFromCamera(new Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera)
      return r
    }
    const surface = (): Intersection | undefined =>
      ray.intersectObjects(scene.children, true).find((h) => h.object instanceof Mesh && shown(h.object) && !('isInstancedMesh' in h.object))
    const snapTo = (e: MouseEvent, r: DOMRect, cands: Point3[]): Point3 | null => {
      const screen = cands.map((p) => {
        const v = new Vector3(...toThree(p)).project(camera)
        return { p, screen: [((v.x + 1) / 2) * r.width, ((1 - v.y) / 2) * r.height] as [number, number], z: v.z }
      }).filter((c) => c.z < 1)
      return nearestSnap([e.clientX - r.left, e.clientY - r.top], screen, 10)?.p ?? null
    }
    const add = (m: Omit<Measurement, 'id'>) => useEditorStore.getState().addMeasurement({ ...m, id: `m${++seq}` })

    const click = (e: MouseEvent) => {
      if (downAt && Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 4) return // orbit drag, not a click
      const s = useEditorStore.getState()
      if (!s.view) return
      const r = cast(e)
      if (tool === 'area') {
        if (e.detail > 1) return
        const hit = ray.ray.intersectPlane(floor, new Vector3())
        const plan: Point3[] = [...(s.view.walls ?? []).flatMap((w): Point3[] => [[w.a[0], w.a[1], 0], [w.b[0], w.b[1], 0]]),
          ...gridIntersections(s.view).map(([x, y]): Point3 => [x, y, 0])]
        const p = snapTo(e, r, plan) ?? (hit ? (fromThree(hit).map(Math.round) as Point3) : null)
        if (p) set([...pendingRef.current, [p[0], p[1], 0]])
        return
      }
      const hit = surface()
      if (!hit) return
      const raw = fromThree(hit.point).map(Math.round) as Point3
      // plan points (wall ends, grid crossings) win over mesh vertices that project to the same pixels, e.g. column tops in Top
      const plan: Point3[] = snapCandidates({ object: new Mesh(), point: hit.point }, s.view, s.layers.axes)
      const p = snapTo(e, r, plan) ?? snapTo(e, r, snapCandidates(hit as never, { ...s.view, walls: [] }, false)) ?? raw
      if (tool === 'distance') {
        const [a] = pendingRef.current
        if (!a) return set([p])
        const b = e.shiftKey ? lockAxis(a, p) : p
        const d = distance(a, b)
        add({ kind: 'distance', points: [a, b], value: d.d,
          label: `${formatM(d.d)} (ΔX ${formatM(Math.abs(d.dx))}, ΔY ${formatM(Math.abs(d.dy))}, ΔZ ${formatM(Math.abs(d.dz))})` })
        return set([])
      }
      if (tool === 'room-area') {
        const room = s.view.rooms?.find((x) => x.id === roomAt(s.view!, raw[0], raw[1]))
        if (!room || room.area_m2 == null) return s.setNotice({ kind: 'info', text: 'Klik lantai ruang' })
        add({ kind: 'room-area', points: room.polygon.map(([x, y]): Point3 => [x, y, 0]), value: room.area_m2,
          label: `${room.name || room.id} ${formatM2(room.area_m2)}` })
        return
      }
      // height
      let text = formatM(p[2])
      if (specTypeOf(hit.object) === 'wall') {
        const w = s.view.walls?.find((x) => x.id === specIdOf(hit.object))
        if (w) text += ` · dinding ${w.id}: ${formatM(w.height ?? s.view.meta.defaults?.wall_height ?? 3000)}`
      }
      add({ kind: 'height', points: [p], value: p[2], label: text })
    }
    const dbl = () => {
      if (tool !== 'area') return
      const pts = pendingRef.current.filter((p, i, a) => i === 0 || Math.hypot(p[0] - a[i - 1][0], p[1] - a[i - 1][1]) > 1)
      if (pts.length >= 3) add({ kind: 'area', points: pts, value: shoelaceM2(pts.map(([x, y]) => [x, y])), label: formatM2(shoelaceM2(pts.map(([x, y]) => [x, y]))) })
      set([])
    }
    const down = (e: PointerEvent) => { downAt = [e.clientX, e.clientY] }
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') set([]) }
    el.addEventListener('pointerdown', down)
    el.addEventListener('click', click)
    el.addEventListener('dblclick', dbl)
    window.addEventListener('keydown', key)
    return () => {
      el.removeEventListener('pointerdown', down)
      el.removeEventListener('click', click)
      el.removeEventListener('dblclick', dbl)
      window.removeEventListener('keydown', key)
    }
  }, [tool, gl, camera, scene])

  return (
    <>
      {measurements.map((m) => <Shape key={m.id} m={m} />)}
      {pending.map((p, i) => (
        <mesh key={i} position={lift(p, 0)} raycast={() => null}>
          <sphereGeometry args={[0.08, 12, 12]} />
          <meshBasicMaterial color={COLOR} depthTest={false} />
        </mesh>
      ))}
      {pending.length > 1 && <Line points={pending.map((p) => lift(p))} color={COLOR} lineWidth={1} dashed depthTest={false} />}
    </>
  )
}
