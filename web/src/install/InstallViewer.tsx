import { Bounds, OrbitControls, useGLTF } from '@react-three/drei'
import { Canvas, useThree } from '@react-three/fiber'
import { Checkbox } from '@carbon/react'
import { Suspense, useEffect, useState } from 'react'
import type { Mesh } from 'three'
import { LAYERS, LAYERS_OFF, layerOf, type Layer } from './layers'
import { keepPerforationVisible } from './perforation'

function Model({ url, on }: { url: string; on: Record<Layer, boolean> }) {
  const { scene } = useGLTF(url)
  const gl = useThree((s) => s.gl)
  useEffect(() => {  // GLBs built before the builder switched to mipmapped sampling are fixed here too
    const aniso = gl.capabilities.getMaxAnisotropy()
    scene.traverse((o) => {
      const mats = (o as Mesh).material
      for (const m of Array.isArray(mats) ? mats : mats ? [mats] : []) keepPerforationVisible(m, aniso)
    })
  }, [scene, gl])
  useEffect(() => {
    scene.traverse((o) => {
      const layer = layerOf(o.name)
      if (layer) o.visible = on[layer]
    })
  }, [scene, on])
  return <primitive object={scene} />
}

/** M12b: the layout with the built installation (layout_installation.glb), layers switched on and off by name. */
export function InstallViewer({ url }: { url: string }) {
  const [on, setOn] = useState(() => Object.fromEntries(LAYERS.map((l) => [l, !LAYERS_OFF.includes(l)])) as Record<Layer, boolean>)
  return (
    <div className="install-viewer">
      <div className="install-viewer__layers" role="group" aria-label="Layer instalasi">
        {LAYERS.map((l) => (
          <Checkbox key={l} id={`iv-${l}`} labelText={l} checked={on[l]} onChange={(_, { checked }) => setOn({ ...on, [l]: checked })} />
        ))}
      </div>
      <Canvas camera={{ position: [20, 18, 20], fov: 45, near: 0.05, far: 2000 }}>
        <color attach="background" args={['#161616']} />
        <ambientLight intensity={0.7} />
        <directionalLight position={[30, 40, 20]} intensity={1.6} />
        <Suspense fallback={null}>
          <Bounds fit clip observe margin={1.1}><Model url={url} on={on} /></Bounds>
        </Suspense>
        <OrbitControls makeDefault />
      </Canvas>
    </div>
  )
}
