import type { Spec } from '../../types/spec'

type Pt = [number, number]

/** Python's round(): ties go to the even neighbour, so client mm values match the server's. */
export function roundHalfEven(v: number): number {
  const f = Math.floor(v)
  const d = v - f
  if (d > 0.5) return f + 1
  if (d < 0.5) return f
  return f % 2 === 0 ? f : f + 1
}

function onSegment(p: Pt, a: Pt, b: Pt): boolean {
  const cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
  if (Math.abs(cross) > 1e-9 * Math.max(1, Math.hypot(b[0] - a[0], b[1] - a[1]))) return false
  return Math.min(a[0], b[0]) <= p[0] && p[0] <= Math.max(a[0], b[0])
    && Math.min(a[1], b[1]) <= p[1] && p[1] <= Math.max(a[1], b[1])
}

export function pointInPolygon(p: Pt, poly: Pt[]): 'inside' | 'boundary' | 'outside' {
  let inside = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[j], b = poly[i]
    if (onSegment(p, a, b)) return 'boundary'
    if ((b[1] > p[1]) !== (a[1] > p[1]) && p[0] < ((a[0] - b[0]) * (p[1] - b[1])) / (a[1] - b[1]) + b[0]) inside = !inside
  }
  return inside ? 'inside' : 'outside'
}

/** First room (spec order) whose shape covers the point, like shapely `covers` in core/spec/derive.py. */
export function roomAt(spec: Spec, x: number, y: number): string | null {
  for (const r of spec.rooms ?? []) {
    if (pointInPolygon([x, y], r.polygon as Pt[]) === 'outside') continue
    if ((r.holes ?? []).some((h) => pointInPolygon([x, y], h as Pt[]) === 'inside')) continue
    return r.id
  }
  return null
}
