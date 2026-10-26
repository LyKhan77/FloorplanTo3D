import { useGLTF } from '@react-three/drei'
import type { ThreeEvent } from '@react-three/fiber'
import { useEffect, useMemo } from 'react'
import { EdgesGeometry, Mesh, Plane, Vector3, type Material, type Object3D } from 'three'
import { fromThree } from '../lib/coords'
import { roomAt } from '../lib/geom'
import { useEditorStore } from '../store'
import { applyShellState, buildShellIndex, specIdOf, specTypeOf } from './shellIndex'

const SELECTABLE = new Set(['wall', 'door', 'window', 'column', 'room', 'stair'])
const edgesCache = new WeakMap<Mesh, EdgesGeometry>()
const edgesOf = (m: Mesh) => edgesCache.get(m) ?? edgesCache.set(m, new EdgesGeometry(m.geometry, 30)).get(m)!

/** Keeps points below the plane: y <= constant (meters). */
const cutPlane = new Plane(new Vector3(0, -1, 0), Infinity)

export function Shell({ url }: { url: string }) {
  const { scene } = useGLTF(url)
  const index = useMemo(() => buildShellIndex(scene), [scene])
  const view = useEditorStore((s) => s.view)
  const base = useEditorStore((s) => s.base)
  const layers = useEditorStore((s) => s.layers)
  const cutaway = useEditorStore((s) => s.cutaway)
  const selection = useEditorStore((s) => s.selection)

  // Wall materials get their own copy so the cutaway plane clips walls only.
  useEffect(() => {
    const byType: Record<string, number> = {}
    scene.traverse((o) => {
      const t = o.userData?.spec_type
      if (typeof t === 'string') byType[t] = (byType[t] ?? 0) + 1
      if (o instanceof Mesh && specTypeOf(o) === 'wall' && !o.userData.clipped) {
        o.material = (o.material as Material).clone()
        ;(o.material as Material).clippingPlanes = [cutPlane]
        o.userData.clipped = true
      }
    })
    if (import.meta.env.DEV) {
      const w = window as unknown as { __editorStats?: Record<string, unknown> }
      w.__editorStats = { ...w.__editorStats, byType }
    }
  }, [scene])

  useEffect(() => {
    cutPlane.constant = cutaway === null ? Infinity : cutaway / 1000
  }, [cutaway])

  useEffect(() => {
    if (!view || !base) return
    useEditorStore.getState().setPreviewBanner(applyShellState(index, base, view, layers))
  }, [index, view, base, layers])

  const selectedMeshes = useMemo(
    () => selection.flatMap((id) => (index.get(id) ?? []).filter((o): o is Mesh => o instanceof Mesh && o.visible)),
    [selection, index, view, layers], // eslint-disable-line react-hooks/exhaustive-deps
  )

  const onClick = (e: ThreeEvent<MouseEvent>) => {
    const s = useEditorStore.getState()
    if (s.tool !== 'select' || s.mode === 'walk') return
    e.stopPropagation()
    const id = specIdOf(e.object)
    if (id && SELECTABLE.has(specTypeOf(e.object) ?? '')) s.select([id], e.shiftKey)
    else if (!e.shiftKey) s.select([])
  }
  const onPointerMove = (e: ThreeEvent<PointerEvent>) => {
    const s = useEditorStore.getState()
    const [x, y] = fromThree(e.point)
    s.setCursor([Math.round(x), Math.round(y)], s.view ? roomAt(s.view, x, y) : null)
  }

  return (
    <>
      <primitive object={scene} onClick={onClick} onPointerMove={onPointerMove} />
      {selectedMeshes.map((m) => <Outline key={m.uuid} mesh={m} />)}
    </>
  )
}

function Outline({ mesh }: { mesh: Object3D & Mesh }) {
  mesh.updateWorldMatrix(true, false)
  return (
    <lineSegments geometry={edgesOf(mesh)} matrix={mesh.matrixWorld} matrixAutoUpdate={false} renderOrder={10}>
      <lineBasicMaterial color="#0f62fe" depthTest={false} transparent />
    </lineSegments>
  )
}
