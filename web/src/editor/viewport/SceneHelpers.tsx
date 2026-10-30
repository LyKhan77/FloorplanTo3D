import { Grid, Html, Line } from '@react-three/drei'
import { useMemo } from 'react'
import { toThree } from '../lib/coords'
import { labelAt } from '../lib/geom'
import { useEditorStore } from '../store'
import { specBounds } from './bounds'

/** Grid 600 mm, structural grid axes and room labels (layers grid / axes / labels). */
export function SceneHelpers() {
  const view = useEditorStore((s) => s.view)
  const layers = useEditorStore((s) => s.layers)
  const axes = view?.grid?.axes ?? []
  const b = useMemo(() => (view ? specBounds(view) : null), [view])
  if (!view || !b) return null
  const pad = 2000
  return (
    <>
      {layers.grid && (
        <Grid position={[0, 0.002, 0]} cellSize={0.6} sectionSize={6} infiniteGrid fadeDistance={200}
          cellColor="#393939" sectionColor="#6f6f6f" cellThickness={0.6} sectionThickness={1} />
      )}
      {layers.axes && axes.map((a) => {
        const [p, q] = a.orientation === 'vertical'
          ? [[a.offset, b.minY - pad], [a.offset, b.maxY + pad]]
          : [[b.minX - pad, a.offset], [b.maxX + pad, a.offset]]
        return (
          <group key={a.id}>
            <Line points={[toThree([p[0], p[1], 10]), toThree([q[0], q[1], 10])]} color="#8a3ffc" lineWidth={1} dashed dashSize={0.4} gapSize={0.2} />
            <Html position={toThree([q[0], q[1], 10])} center className="editor-axis-label">{a.label}</Html>
          </group>
        )
      })}
      {layers.labels && (view.rooms ?? []).filter((r) => r.name).map((r) => (
        <Html key={r.id} position={toThree([...labelAt(r), 50])} center className="editor-room-label">
          {r.name}
        </Html>
      ))}
    </>
  )
}
