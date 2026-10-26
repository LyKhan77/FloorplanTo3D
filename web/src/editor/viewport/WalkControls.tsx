import { PointerLockControls } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import { Euler, Mesh, Raycaster, Vector3, type Object3D } from 'three'
import { fromThree, toThree } from '../lib/coords'
import { walkStep } from '../lib/walk'
import { useEditorStore } from '../store'
import { specTypeOf } from './shellIndex'

export const EYE = 1.6 // m

const KEYS: Record<string, [number, number]> = {
  KeyW: [1, 0], ArrowUp: [1, 0], KeyS: [-1, 0], ArrowDown: [-1, 0], KeyD: [0, 1], ArrowRight: [0, 1], KeyA: [0, -1], ArrowLeft: [0, -1],
}

/** First-person walk: pointer lock, WASD/arrows, Shift runs; walls stop you 0.3 m short; Esc returns to Orbit. */
export function WalkControls() {
  const { camera, scene } = useThree()
  const held = useRef(new Set<string>())
  const walls = useMemo(() => {
    const out: Object3D[] = []
    scene.traverse((o) => { if (o instanceof Mesh && specTypeOf(o) === 'wall') out.push(o) })
    return out
  }, [scene])

  useEffect(() => {
    const down = (e: KeyboardEvent) => held.current.add(e.code)
    const up = (e: KeyboardEvent) => held.current.delete(e.code)
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
    }
  }, [])

  useFrame((_, dt) => {
    let f = 0, r = 0
    for (const k of held.current) {
      const v = KEYS[k]
      if (v) { f += v[0]; r += v[1] }
    }
    if (!f && !r) return
    const yaw = new Euler().setFromQuaternion(camera.quaternion, 'YXZ').y
    const [x, y] = fromThree(camera.position)
    const ray = new Raycaster()
    const blocked = (from: [number, number], to: [number, number]) => {
      const a = new Vector3(...toThree([from[0], from[1], 1000])), b = new Vector3(...toThree([to[0], to[1], 1000]))
      const dir = b.clone().sub(a)
      const len = dir.length()
      ray.set(a, dir.normalize())
      ray.far = len + 0.3
      return ray.intersectObjects(walls, false).some((h) => h.object.visible)
    }
    const [nx, ny] = walkStep([x, y], yaw, { f, r }, Math.min(dt, 0.1), held.current.has('ShiftLeft') || held.current.has('ShiftRight'), blocked)
    const p = toThree([nx, ny, EYE * 1000])
    camera.position.set(p[0], p[1], p[2])
  })

  return <PointerLockControls makeDefault selector=".editor__canvas-wrap canvas" onUnlock={() => useEditorStore.getState().setMode('orbit')} />
}
