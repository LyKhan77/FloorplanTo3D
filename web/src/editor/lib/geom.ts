import type { Room, Spec } from '../../types/spec'

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

/** Where a room's name is drawn: the OCR label position, else a point inside the room (rooms named in the editor
 *  have none). The area centroid when it lies inside, else the middle of the widest span across the centroid's row. */
export function labelAt(room: Pick<Room, 'polygon' | 'label_pos'>): Pt {
  if (room.label_pos) return [room.label_pos[0], room.label_pos[1]]
  const poly = room.polygon as Pt[]
  let a = 0, cx = 0, cy = 0
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const k = poly[j][0] * poly[i][1] - poly[i][0] * poly[j][1]
    a += k
    cx += (poly[j][0] + poly[i][0]) * k
    cy += (poly[j][1] + poly[i][1]) * k
  }
  if (!a) return poly[0]
  const c: Pt = [cx / (3 * a), cy / (3 * a)]
  if (pointInPolygon(c, poly) === 'inside') return c
  const xs: number[] = []
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [p, q] = [poly[j], poly[i]]
    if ((p[1] > c[1]) !== (q[1] > c[1])) xs.push(p[0] + ((c[1] - p[1]) * (q[0] - p[0])) / (q[1] - p[1]))
  }
  xs.sort((u, v) => u - v)
  let best: Pt = poly[0], width = -1
  for (let i = 0; i + 1 < xs.length; i += 2) {
    if (xs[i + 1] - xs[i] > width) { width = xs[i + 1] - xs[i]; best = [(xs[i] + xs[i + 1]) / 2, c[1]] }
  }
  return best
}

