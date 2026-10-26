import type { Spec } from '../../types/spec'

type P3 = [number, number, number] | number[]

export function distance(a: P3, b: P3): { d: number; dx: number; dy: number; dz: number } {
  const dx = b[0] - a[0], dy = b[1] - a[1], dz = (b[2] ?? 0) - (a[2] ?? 0)
  return { d: Math.hypot(dx, dy, dz), dx, dy, dz }
}

/** Shift-lock: keep only the component with the largest delta. */
export function lockAxis(a: P3, b: P3): [number, number, number] {
  const deltas = [0, 1, 2].map((i) => Math.abs((b[i] ?? 0) - (a[i] ?? 0)))
  const axis = deltas.indexOf(Math.max(...deltas))
  const out: [number, number, number] = [a[0], a[1], a[2] ?? 0]
  out[axis] = b[axis] ?? 0
  return out
}

export function shoelaceM2(points: [number, number][] | number[][]): number {
  let s = 0
  points.forEach((p, i) => {
    const q = points[(i + 1) % points.length]
    s += p[0] * q[1] - q[0] * p[1]
  })
  return Math.abs(s) / 2 / 1e6
}

export const formatM = (mm: number): string => `${(mm / 1000).toFixed(3)} m`
export const formatM2 = (m2: number): string => `${m2.toFixed(2)} m²`

export function nearestSnap<T extends { screen: [number, number] }>(cursor: [number, number], candidates: T[], maxPx = 10): T | null {
  let best: T | null = null, bestD = maxPx
  for (const c of candidates) {
    const d = Math.hypot(c.screen[0] - cursor[0], c.screen[1] - cursor[1])
    if (d <= bestD) [best, bestD] = [c, d]
  }
  return best
}

export function gridIntersections(spec: Spec): [number, number][] {
  const axes = spec.grid?.axes ?? []
  const xs = axes.filter((a) => a.orientation === 'vertical').map((a) => a.offset)
  const ys = axes.filter((a) => a.orientation === 'horizontal').map((a) => a.offset)
  return xs.flatMap((x) => ys.map((y): [number, number] => [x, y]))
}
