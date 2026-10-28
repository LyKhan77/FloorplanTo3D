import { Line } from '@react-three/drei'
import { useThree } from '@react-three/fiber'
import { useEffect } from 'react'
import { Plane, Raycaster, Vector2, Vector3 } from 'three'
import { fromThree, toThree } from '../lib/coords'
import { roundHalfEven } from '../lib/geom'
import { ignoredTarget } from '../lib/keys'
import { gridIntersections, nearestSnap } from '../lib/measure'
import { useEditorStore } from '../store'

const floor = new Plane(new Vector3(0, 1, 0), 0)
type Pt = [number, number]

/** Top mode: two clicks fill the add-wall draft (snap to grid crossings and wall ends within 10 px, else 100 mm);
 * Enter adds the wall and starts the next at its end, Esc stops. */
export function AddWallTool() {
  const { gl, camera } = useThree()
  const draft = useEditorStore((s) => s.wallDraft)

  useEffect(() => {
    const el = gl.domElement
    const ray = new Raycaster()
    const click = (e: MouseEvent) => {
      const s = useEditorStore.getState()
      if (!s.view) return
      const r = el.getBoundingClientRect()
      ray.setFromCamera(new Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera)
      const hit = ray.ray.intersectPlane(floor, new Vector3())
      if (!hit) return
      const cands: Pt[] = [...gridIntersections(s.view), ...(s.view.walls ?? []).flatMap((w) => [w.a as Pt, w.b as Pt])]
      const snapped = nearestSnap([e.clientX - r.left, e.clientY - r.top], cands.map((p) => {
        const v = new Vector3(...toThree([p[0], p[1], 0])).project(camera)
        return { p, screen: [((v.x + 1) / 2) * r.width, ((1 - v.y) / 2) * r.height] as Pt }
      }), 10)?.p
      const [x, y] = fromThree(hit)
      const p: Pt = snapped ? [snapped[0], snapped[1]] : [roundHalfEven(x / 100) * 100, roundHalfEven(y / 100) * 100]
      const d = s.wallDraft
      s.setWallDraft(!d.a || d.b ? { a: p } : { ...d, b: p })
    }
    const key = (e: KeyboardEvent) => {
      const s = useEditorStore.getState()
      if (e.key === 'Enter' && !ignoredTarget(e.target as Element | null)) s.commitWallDraft()
      if (e.key !== 'Escape') return
      s.setWallDraft({})
      s.setTool('select')
    }
    el.addEventListener('click', click)
    window.addEventListener('keydown', key)
    return () => {
      el.removeEventListener('click', click)
      window.removeEventListener('keydown', key)
    }
  }, [gl, camera])

  const pts = [draft.a, draft.b].filter((p): p is Pt => !!p).map((p) => toThree([p[0], p[1], 10]))
  return (
    <>
      {pts.map((p, i) => (
        <mesh key={i} position={p} raycast={() => null}>
          <sphereGeometry args={[0.1, 12, 12]} />
          <meshBasicMaterial color="#ff832b" depthTest={false} />
        </mesh>
      ))}
      {pts.length === 2 && <Line points={pts} color="#ff832b" lineWidth={3} depthTest={false} />}
    </>
  )
}
