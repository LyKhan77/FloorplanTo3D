import { BoxGeometry, Mesh, Vector3 } from 'three'
import { describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { gridIntersections } from './measure'
import { snapCandidates } from './snapCandidates'

const gt = gtJson as unknown as Spec
const noWalls: Spec = { ...gt, walls: [] }

function box() {
  const m = new Mesh(new BoxGeometry(1, 1, 1))
  m.position.set(2, 0, -3)
  m.updateMatrixWorld(true)
  return m
}

describe('snapCandidates', () => {
  it('includes world vertices of the hit mesh in spec mm', () => {
    const c = snapCandidates({ object: box(), point: new Vector3(2.5, 0.2, -3) }, noWalls, false)
    expect(c).toContainEqual([2500, 3500, 500])
    expect(c).toContainEqual([1500, 2500, -500])
  })

  it('adds edge midpoints of the hit triangle', () => {
    const c = snapCandidates({ object: box(), point: new Vector3(2.5, 0.2, -3), face: { a: 0, b: 1, c: 2 } }, noWalls, false)
    // BoxGeometry +X face: vertices 0 (2.5,0.5,-2.5) and 1 (2.5,0.5,-3.5) → midpoint (2.5, 0.5, -3)
    expect(c).toContainEqual([2500, 3000, 500])
  })

  it('axes and wall ends add plan points at z = 0', () => {
    const plain = snapCandidates({ object: box(), point: new Vector3() }, gt, false)
    const w1 = gt.walls![0]
    expect(plain).toContainEqual([w1.a[0], w1.a[1], 0])
    const withAxes = snapCandidates({ object: box(), point: new Vector3() }, gt, true)
    expect(withAxes.length - plain.length).toBe(gridIntersections(gt).length)
  })
})
