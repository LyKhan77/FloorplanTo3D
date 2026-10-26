import { Euler, Vector3 } from 'three'
import { describe, expect, it } from 'vitest'
import { Quaternion } from 'three'
import { fromThree, rotToThree, toThree, yawOf } from './coords'

describe('coords', () => {
  it('maps spec mm (Z-up) to three meters (Y-up) and back', () => {
    expect(toThree([1000, 2000, 500])).toEqual([1, 0.5, -2])
    expect(toThree([1000, 2000])).toEqual([1, 0, -2])
    expect(fromThree({ x: 1, y: 0.5, z: -2 })).toEqual([1000, 2000, 500])
    expect(fromThree({ x: 0, y: 0, z: 0 })).toEqual([0, 0, 0])
  })

  it('spec rotation (CCW about +Z) is rotation.y in three', () => {
    const front = new Vector3(...toThree([0, 1000, 0])).applyEuler(new Euler(0, rotToThree(90), 0))
    const [x, y] = fromThree(front)
    expect(x).toBeCloseTo(-1000)
    expect(y).toBeCloseTo(0)
  })
})

describe('yawOf', () => {
  it('reads Y rotations past ±90° (XYZ Euler would flip them)', () => {
    for (const deg of [30, 120, 180, -150]) {
      const q = new Quaternion().setFromEuler(new Euler(0, rotToThree(deg), 0))
      const got = (yawOf(q) * 180) / Math.PI
      expect(((got - deg) % 360 + 540) % 360 - 180).toBeCloseTo(0)
    }
  })
})
