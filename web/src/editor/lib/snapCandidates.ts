import { Vector3, type Mesh } from 'three'
import type { Spec } from '../../types/spec'
import { fromThree } from './coords'
import { gridIntersections } from './measure'

type P3 = [number, number, number]

/** Measure snap points in spec mm: hit mesh vertices, hit triangle edge midpoints, wall ends, grid crossings. */
export function snapCandidates(hit: { object: Mesh; point: Vector3; face?: { a: number; b: number; c: number } | null },
  spec: Spec, axesVisible: boolean): P3[] {
  const out: P3[] = []
  const pos = hit.object.geometry?.attributes?.position
  const world = (i: number) => new Vector3().fromBufferAttribute(pos, i).applyMatrix4(hit.object.matrixWorld)
  if (pos) {
    for (let i = 0; i < pos.count; i++) out.push(fromThree(world(i)).map(Math.round) as P3)
    if (hit.face) {
      const [a, b, c] = [hit.face.a, hit.face.b, hit.face.c].map(world)
      for (const [p, q] of [[a, b], [b, c], [c, a]]) out.push(fromThree(p.clone().add(q).multiplyScalar(0.5)).map(Math.round) as P3)
    }
  }
  for (const w of spec.walls ?? []) out.push([w.a[0], w.a[1], 0], [w.b[0], w.b[1], 0])
  if (axesVisible) for (const [x, y] of gridIntersections(spec)) out.push([x, y, 0])
  return out
}
