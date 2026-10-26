import { MapControls, OrbitControls, OrthographicCamera, PerspectiveCamera } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Suspense, useCallback, useEffect, useMemo, useRef } from 'react'
import { MOUSE, type Camera } from 'three'
import { toThree } from '../lib/coords'
import { useEditorStore } from '../store'
import { specBounds, type Bounds } from './bounds'
import type { Template } from '../../api/types'
import { DropGhost } from './DropGhost'
import { justDragged } from './gizmoState'
import { Marquee } from './Marquee'
import { MeasureLayer } from './MeasureLayer'
import { TransformGizmo } from './TransformGizmo'
import { ObjectsLayer } from './ObjectsLayer'
import { SceneHelpers } from './SceneHelpers'
import { Shell } from './Shell'

function CameraRig({ bounds }: { bounds: Bounds }) {
  const mode = useEditorStore((s) => s.mode)
  const size = useThree((s) => s.size)
  const cx = (bounds.minX + bounds.maxX) / 2, cy = (bounds.minY + bounds.maxY) / 2
  const center = toThree([cx, cy, 0])
  const w = (bounds.maxX - bounds.minX) / 1000, d = (bounds.maxY - bounds.minY) / 1000
  if (mode === 'top') {
    const zoom = Math.min(size.width / w, size.height / d) * 0.9
    return (
      <>
        {/* a hair south of straight down keeps north (-Z) at the top of the screen */}
        <OrthographicCamera makeDefault position={[center[0], 200, center[2] + 0.001]} zoom={zoom} near={0.1} far={1000} />
        {/* left button is the marquee in Top; pan with the right button */}
        <MapControls makeDefault target={center} enableRotate={false} screenSpacePanning zoomToCursor
          mouseButtons={{ MIDDLE: MOUSE.DOLLY, RIGHT: MOUSE.PAN }} />
      </>
    )
  }
  const r = Math.max(w, d)
  return (
    <>
      <PerspectiveCamera makeDefault position={[center[0] + r * 0.4, r * 0.7, center[2] + r * 0.8]} fov={50} near={0.1} far={2000} />
      <OrbitControls makeDefault target={center} maxPolarAngle={Math.PI / 2 - 0.05} />
    </>
  )
}

function CameraBridge({ onCamera }: { onCamera(c: Camera): void }) {
  const current = useThree((s) => s.camera)
  useEffect(() => onCamera(current), [onCamera, current])
  return null
}

function FpsMeter() {
  const acc = useRef({ frames: 0, t: 0 })
  useFrame((_, dt) => {
    acc.current.frames++
    acc.current.t += dt
    if (acc.current.t < 1) return
    const fps = acc.current.frames / acc.current.t
    acc.current = { frames: 0, t: 0 }
    useEditorStore.getState().setFps(fps)
    if (import.meta.env.DEV) {
      const w = window as unknown as { __editorStats?: Record<string, unknown> }
      w.__editorStats = { ...w.__editorStats, fps }
    }
  })
  return null
}

export function Viewport({ shellUrl, templates }: { shellUrl: string; templates: Template[] }) {
  const base = useEditorStore((s) => s.base)
  const outline = base?.meta.building_outline
  const bounds = useMemo(() => (base ? specBounds(base) : null), [outline]) // eslint-disable-line react-hooks/exhaustive-deps
  const tool = useEditorStore((s) => s.tool)
  const wrap = useRef<HTMLDivElement>(null)
  const camera = useRef<Camera | null>(null)
  const setCamera = useCallback((c: Camera) => { camera.current = c }, [])
  if (!bounds) return null
  return (
    <div ref={wrap} className="editor__canvas-wrap">
    <Canvas dpr={[1, 2]} onCreated={({ gl }) => { gl.localClippingEnabled = true }}
      onPointerMissed={(e) => { if (e.type === 'click' && useEditorStore.getState().tool === 'select' && !justDragged()) useEditorStore.getState().select([]) }}>
      <color attach="background" args={['#161616']} />
      <hemisphereLight intensity={0.9} groundColor="#3d3d3d" />
      <directionalLight position={[30, 60, 20]} intensity={1.4} />
      <Suspense fallback={null}><Shell url={shellUrl} /></Suspense>
      <ObjectsLayer templates={templates} />
      <DropGhost templates={templates} />
      <TransformGizmo templates={templates} />
      <MeasureLayer key={tool} />
      <CameraBridge onCamera={setCamera} />
      <SceneHelpers />
      <CameraRig bounds={bounds} />
      <FpsMeter />
    </Canvas>
    <Marquee wrap={wrap} camera={camera} />
    </div>
  )
}
