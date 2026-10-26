import { Line } from '@react-three/drei'
import { useMemo } from 'react'
import type { Wall } from '../../types/spec'
import { toThree } from '../lib/coords'
import { geometryDiff } from '../lib/geometryDiff'
import { useEditorStore } from '../store'

const ORANGE = '#ff832b'
const Z = 10 // mm above the floor
type Pt = [number, number]

const at = ([x, y]: Pt | number[]) => toThree([x, y, Z])

function outline(w: Wall): [number, number, number][] {
  const dx = w.b[0] - w.a[0], dy = w.b[1] - w.a[1]
  const len = Math.hypot(dx, dy) || 1
  const nx = (-dy / len) * (w.thickness / 2), ny = (dx / len) * (w.thickness / 2)
  return ([[w.a[0] + nx, w.a[1] + ny], [w.b[0] + nx, w.b[1] + ny], [w.b[0] - nx, w.b[1] - ny], [w.a[0] - nx, w.a[1] - ny],
    [w.a[0] + nx, w.a[1] + ny]] as Pt[]).map(at)
}

function along(w: Wall, d: number): Pt {
  const len = Math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1]) || 1
  return [w.a[0] + ((w.b[0] - w.a[0]) / len) * d, w.a[1] + ((w.b[1] - w.a[1]) / len) * d]
}

/** Orange 2D overlay of geometry edits the shell cannot show until Save + Regenerate. */
export function GeometryPreview() {
  const base = useEditorStore((s) => s.base)
  const view = useEditorStore((s) => s.view)
  const diff = useMemo(() => (base && view ? geometryDiff(base, view) : null), [base, view])
  if (!diff || !view || !base) return null
  const wallOf = (id: string) => view.walls?.find((w) => w.id === id) ?? base.walls?.find((w) => w.id === id)
  return (
    <group renderOrder={5}>
      {diff.walls.map((d) => (
        <Line key={d.id} points={outline(d.el)} color={ORANGE} lineWidth={2} dashed={d.state === 'deleted'} dashSize={0.2}
          gapSize={0.15} depthTest={false} />
      ))}
      {diff.openings.map((d) => {
        const w = wallOf(d.el.wall_id)
        if (!w) return null
        return <Line key={d.id} points={[at(along(w, d.el.offset)), at(along(w, d.el.offset + d.el.width))]} color={ORANGE}
          lineWidth={5} dashed={d.state === 'deleted'} dashSize={0.1} gapSize={0.1} depthTest={false} />
      })}
      {diff.stairs.flatMap((d) => d.el.flights.map((f, i) => {
        const dx = f.end[0] - f.start[0], dy = f.end[1] - f.start[1]
        const len = Math.hypot(dx, dy) || 1
        const ux = dx / len, uy = dy / len, s = Math.min(600, len / 3)
        const head: Pt[] = [[f.end[0] - ux * s - uy * s * 0.5, f.end[1] - uy * s + ux * s * 0.5], [f.end[0], f.end[1]],
          [f.end[0] - ux * s + uy * s * 0.5, f.end[1] - uy * s - ux * s * 0.5]]
        return (
          <group key={`${d.id}-${i}`}>
            <Line points={[at(f.start), at(f.end)]} color={ORANGE} lineWidth={2} dashed={d.state === 'deleted'} dashSize={0.2}
              gapSize={0.15} depthTest={false} />
            <Line points={head.map(at)} color={ORANGE} lineWidth={2} depthTest={false} />
          </group>
        )
      }))}
    </group>
  )
}
