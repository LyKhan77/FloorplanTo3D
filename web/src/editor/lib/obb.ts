import type { Spec } from '../../types/spec'

type Pt = [number, number]
interface Placed { position: [number, number, number] | number[]; rotation?: number | null; dims: [number, number, number] | number[] }

function box(cx: number, cy: number, w: number, d: number, deg: number): Pt[] {
  const c = Math.cos((deg * Math.PI) / 180), s = Math.sin((deg * Math.PI) / 180)
  return ([[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]] as Pt[])
    .map(([x, y]): Pt => [cx + x * c - y * s, cy + x * s + y * c])
}

/** Object footprint, 4 corners CCW (w along local X, d along local Y, pivot at the center). */
export const footprint = (o: Placed): Pt[] => box(o.position[0], o.position[1], o.dims[0], o.dims[1], o.rotation ?? 0)

/** SAT on convex quads; edges that touch within 1 mm do not count. */
export function overlaps(a: Pt[], b: Pt[], tol = 1): boolean {
  for (const poly of [a, b]) {
    for (let i = 0; i < poly.length; i++) {
      const p = poly[i], q = poly[(i + 1) % poly.length]
      const len = Math.hypot(q[0] - p[0], q[1] - p[1]) || 1
      const n: Pt = [(p[1] - q[1]) / len, (q[0] - p[0]) / len]
      const proj = (pts: Pt[]) => pts.map(([x, y]) => x * n[0] + y * n[1])
      const pa = proj(a), pb = proj(b)
      if (Math.max(...pa) <= Math.min(...pb) + tol || Math.max(...pb) <= Math.min(...pa) + tol) return false
    }
  }
  return true
}

/** Object vs object, wall footprint (a->b, thickness wide) and column box. */
export function collisions(spec: Spec): { a: string; b: string }[] {
  const objs = (spec.objects ?? []).map((o) => ({ id: o.id, fp: footprint(o) }))
  const others = [
    ...(spec.walls ?? []).map((w) => {
      const dx = w.b[0] - w.a[0], dy = w.b[1] - w.a[1]
      const fp = box((w.a[0] + w.b[0]) / 2, (w.a[1] + w.b[1]) / 2, Math.hypot(dx, dy), w.thickness,
        (Math.atan2(dy, dx) * 180) / Math.PI)
      return { id: w.id, fp }
    }),
    // ponytail: circle and h-section columns use their bounding box
    ...(spec.columns ?? []).map((c) => ({ id: c.id, fp: box(c.center[0], c.center[1], c.size[0], c.size[1] ?? c.size[0], c.rotation ?? 0) })),
  ]
  const hits: { a: string; b: string }[] = []
  objs.forEach((o, i) => {
    for (const p of objs.slice(i + 1)) if (overlaps(o.fp, p.fp)) hits.push({ a: o.id, b: p.id })
    for (const x of others) if (overlaps(o.fp, x.fp)) hits.push({ a: o.id, b: x.id })
  })
  return hits
}
