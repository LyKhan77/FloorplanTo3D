import { TransformControls } from '@react-three/drei'
import { useEffect, useMemo, useState } from 'react'
import type { Group } from 'three'
import type { Template } from '../../api/types'
import type { EditorOp } from '../ops/reducer'
import { fromThree, rotToThree, toThree, yawOf } from '../lib/coords'
import { clampDims } from '../lib/resize'
import { gizmoYawDeg, groupCenter, moveOps, rotateOps, templateOf, unlocked } from '../lib/transform'
import { useEditorStore } from '../store'
import { endDrag, gizmoState } from './gizmoState'
import { boxEdges, objectMatrix } from './objectMatrix'


function useAltKey(): boolean {
  const [alt, setAlt] = useState(false)
  useEffect(() => {
    const on = (e: KeyboardEvent) => setAlt(e.altKey)
    window.addEventListener('keydown', on)
    window.addEventListener('keyup', on)
    return () => {
      window.removeEventListener('keydown', on)
      window.removeEventListener('keyup', on)
    }
  }, [])
  return alt
}

/**
 * Gizmo on a proxy group at the selection centre. Dragging previews wireframes only; mouse-up turns the proxy
 * transform into ops (moveOps / rotateOps / clamped dims) or snaps the proxy back with a notice.
 */
export function TransformGizmo({ templates }: { templates: Template[] }) {
  const view = useEditorStore((s) => s.view)
  const selection = useEditorStore((s) => s.selection)
  const gizmo = useEditorStore((s) => s.gizmo)
  const tool = useEditorStore((s) => s.tool)
  const viewMode = useEditorStore((s) => s.mode)
  const alt = useAltKey()
  const [proxy, setProxy] = useState<Group | null>(null)
  const objs = useMemo(() => unlocked((view?.objects ?? []).filter((o) => selection.includes(o.id))), [view, selection])
  if (!objs.length || tool !== 'select' || viewMode === 'walk') return null

  const [cx, cy] = groupCenter(objs)
  const single = objs.length === 1 ? objs[0] : null
  const t = single ? templateOf(single, templates) : undefined
  const mode = gizmo === 'scale' && !single ? 'translate' : gizmo
  const resizable = (k: 'w' | 'd' | 'h') => !!t && t.scale_mode !== 'fixed' && !!t.resizable?.[k]
  const yaw = gizmoYawDeg(objs, mode)
  const key = `${mode}|` + objs.map((o) => `${o.id}:${o.position}:${o.rotation}:${o.dims}`).join('|')

  const reset = () => {
    if (!proxy) return
    proxy.position.set(...toThree([cx, cy, 0]))
    proxy.rotation.set(0, rotToThree(yaw), 0)
    proxy.scale.set(1, 1, 1)
  }
  const commit = () => {
    endDrag()
    const s = useEditorStore.getState()
    if (!proxy || !s.view) return
    let ops: EditorOp[] | { error: string }
    if (mode === 'translate') {
      const [x, y] = fromThree(proxy.position)
      ops = moveOps(objs, [x - cx, y - cy], s.view, s.snap && !alt, templates)
    } else if (mode === 'rotate') {
      ops = rotateOps(objs, Math.round((yawOf(proxy.quaternion) * 180) / Math.PI * 10) / 10)
    } else {
      const o = single!
      const dims: [number, number, number] = [Math.round(o.dims[0] * proxy.scale.x), Math.round(o.dims[1] * proxy.scale.z),
        Math.round(o.dims[2] * proxy.scale.y)]
      ops = [{ op: 'update_object', id: o.id, dims: t ? clampDims(dims, t) : dims }]
    }
    if ('error' in ops) s.setNotice({ kind: 'error', text: ops.error })
    if ('error' in ops || !ops.length || !s.applyMany(ops)) reset()
  }

  return (
    <>
      <group key={key} ref={setProxy} position={toThree([cx, cy, 0])} rotation={[0, rotToThree(yaw), 0]}>
        {objs.map((o) => (
          <lineSegments key={o.id} geometry={boxEdges} matrixAutoUpdate={false} raycast={() => null}
            matrix={objectMatrix({ ...o, rotation: (o.rotation ?? 0) - yaw, position: [o.position[0] - cx, o.position[1] - cy, o.position[2]] }, undefined)}>
            <lineBasicMaterial color="#78a9ff" depthTest={false} transparent />
          </lineSegments>
        ))}
      </group>
      {proxy && (
        <TransformControls key={`${key}:gizmo`} object={proxy} mode={mode} size={0.8}
          showX={mode === 'translate' || (mode === 'scale' && resizable('w'))}
          showY={mode === 'rotate' || (mode === 'scale' && resizable('h'))}
          showZ={mode === 'translate' || (mode === 'scale' && resizable('d'))}
          rotationSnap={alt ? null : Math.PI / 12} onMouseDown={() => { gizmoState.dragging = true }} onMouseUp={commit} />
      )}
    </>
  )
}
