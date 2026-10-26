import { Quaternion, Vector3 } from 'three'
import { describe, expect, it } from 'vitest'
import type { Template } from '../../api/types'
import type { PlacedObject } from '../../types/spec'
import { objectMatrix, shouldInstance } from './objectMatrix'

const t: Template = { id: 'rack', version: '1.0.0', name: 'Rack', category: 'rack', thumbnail_url: '', asset_url: '',
  dims: { w: 600, d: 1200, h: 2000 } }
const o: PlacedObject = { id: 'O1', template_id: 'rack', template_version: '1.0.0', position: [1000, 2000, 0], rotation: 90,
  dims: [600, 1100, 2000] }

function parts(m: ReturnType<typeof objectMatrix>) {
  const p = new Vector3(), q = new Quaternion(), s = new Vector3()
  m.decompose(p, q, s)
  return { p, q, s }
}

describe('objectMatrix', () => {
  it('objectMatrix places, rotates and scales like the builder', () => {
    const { p, q, s } = parts(objectMatrix(o, t))
    expect(p.toArray().map((v) => +v.toFixed(6))).toEqual([1, 0, -2])
    expect(q.angleTo(new Quaternion().setFromAxisAngle(new Vector3(0, 1, 0), Math.PI / 2))).toBeLessThan(1e-6)
    expect(s.x).toBeCloseTo(1)
    expect(s.y).toBeCloseTo(1)
    expect(s.z).toBeCloseTo(1100 / 1200)
  })

  it('without a template the unit box is scaled to dims', () => {
    const { s } = parts(objectMatrix({ ...o, rotation: 0 }, undefined))
    expect(s.toArray().map((v) => +v.toFixed(6))).toEqual([0.6, 2, 1.1])
  })

  it('instances above 20 per template', () => {
    expect(shouldInstance(20)).toBe(false)
    expect(shouldInstance(21)).toBe(true)
  })
})
