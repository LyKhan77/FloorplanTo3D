import type { Spec } from '../../types/spec'

export interface Bounds { minX: number; maxX: number; minY: number; maxY: number }

/** Building extent in mm: building_outline, else wall endpoints. */
export function specBounds(spec: Spec): Bounds {
  const pts = (spec.meta.building_outline ?? []).flat() as number[][]
  const all = pts.length ? pts : (spec.walls ?? []).flatMap((w) => [w.a, w.b])
  const xs = all.map((p) => p[0]), ys = all.map((p) => p[1])
  if (!xs.length) return { minX: -5000, maxX: 5000, minY: -5000, maxY: 5000 }
  return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) }
}
