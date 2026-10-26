import { useThree } from '@react-three/fiber'
import { useEffect, useState } from 'react'
import { Plane, Raycaster, Vector2, Vector3 } from 'three'
import type { Template } from '../../api/types'
import { fromThree } from '../lib/coords'
import { planDrop } from '../lib/drop'
import { snapPosition } from '../lib/snap'
import { useEditorStore } from '../store'
import { objectMatrix, unitBox } from './objectMatrix'

const floor = new Plane(new Vector3(0, 1, 0), 0)

/** HTML drag & drop from the library onto the canvas: ghost box at the snapped spot, add_object on drop. */
export function DropGhost({ templates }: { templates: Template[] }) {
  const { gl, camera } = useThree()
  const dragging = useEditorStore((s) => s.dragging)
  const [at, setAt] = useState<[number, number] | null>(null)

  useEffect(() => {
    const el = gl.domElement
    const ray = new Raycaster()
    const planPoint = (e: DragEvent): [number, number] | null => {
      const r = el.getBoundingClientRect()
      ray.setFromCamera(new Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera)
      const hit = ray.ray.intersectPlane(floor, new Vector3())
      if (!hit) return null
      const [x, y] = fromThree(hit)
      return [x, y]
    }
    const templateOf = (e: DragEvent) => {
      const key = e.dataTransfer?.getData('application/x-template')
      return templates.find((t) => `${t.id}@${t.version}` === key) ?? useEditorStore.getState().dragging
    }
    const over = (e: DragEvent) => {
      const s = useEditorStore.getState()
      if (!s.dragging) return
      e.preventDefault()
      const p = planPoint(e)
      setAt(p && snapPosition(p, [s.dragging.dims.w, s.dragging.dims.d, s.dragging.dims.h], 0,
        s.dragging.snap ?? { grid_mm: 600, align: 'edge' }, s.snap && !e.altKey))
    }
    const drop = (e: DragEvent) => {
      e.preventDefault()
      setAt(null)
      const s = useEditorStore.getState()
      const t = templateOf(e)
      const p = planPoint(e)
      s.setDragging(null)
      if (!t || !p || !s.view) return
      const r = planDrop(s.view, t, p, s.snap && !e.altKey)
      if ('error' in r) return s.setNotice({ kind: 'error', text: r.error })
      if (s.apply(r.op)) {
        s.select([])
        if (r.warning) s.setNotice({ kind: 'warning', text: r.warning })
      }
    }
    const leave = () => setAt(null)
    el.addEventListener('dragover', over)
    el.addEventListener('drop', drop)
    el.addEventListener('dragleave', leave)
    return () => {
      el.removeEventListener('dragover', over)
      el.removeEventListener('drop', drop)
      el.removeEventListener('dragleave', leave)
    }
  }, [gl, camera, templates])

  if (!dragging || !at) return null
  const m = objectMatrix({ position: [at[0], at[1], 0], rotation: 0, dims: [dragging.dims.w, dragging.dims.d, dragging.dims.h] }, undefined)
  return (
    <mesh geometry={unitBox} matrix={m} matrixAutoUpdate={false} raycast={() => null}>
      <meshBasicMaterial color="#0f62fe" transparent opacity={0.35} depthWrite={false} />
    </mesh>
  )
}
