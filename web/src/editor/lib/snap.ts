import { roundHalfEven } from './geom'

/** PRD/10 §3: edge = footprint corner on the grid (90° multiples only), center = pivot on the grid. */
export function snapPosition(p: [number, number], dims: [number, number, number], rotationDeg: number,
  snap: { grid_mm: number; align: 'edge' | 'center' }, enabled: boolean): [number, number] {
  if (!enabled) return p
  const g = snap.grid_mm
  const toGrid = (v: number) => roundHalfEven(v / g) * g
  const r = ((rotationDeg % 360) + 360) % 360
  if (snap.align === 'center' || r % 90 !== 0) return [toGrid(p[0]), toGrid(p[1])]
  const [fw, fd] = r === 90 || r === 270 ? [dims[1], dims[0]] : [dims[0], dims[1]]
  return [toGrid(p[0] - fw / 2) + fw / 2, toGrid(p[1] - fd / 2) + fd / 2]
}
