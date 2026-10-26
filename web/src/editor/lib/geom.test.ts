import { describe, expect, it } from 'vitest'
import type { Polygon, Spec } from '../../types/spec'
import { pointInPolygon, roomAt, roundHalfEven } from './geom'

const square = (x0: number, y0: number, x1: number, y1: number): Polygon => [
  [x0, y0], [x1, y0], [x1, y1], [x0, y1],
]

function specWith(rooms: Spec['rooms']): Spec {
  return { meta: {} as Spec['meta'], rooms }
}

describe('geom', () => {
  it('roomAt matches server covers semantics (holes, boundary, outside)', () => {
    const spec = specWith([{ id: 'R1', polygon: square(0, 0, 1000, 1000), holes: [square(400, 400, 600, 600)] }])
    expect(roomAt(spec, 500, 500)).toBeNull()
    expect(roomAt(spec, 400, 500)).toBe('R1')
    expect(roomAt(spec, 0, 500)).toBe('R1')
    expect(roomAt(spec, 200, 200)).toBe('R1')
    expect(roomAt(spec, -1, 0)).toBeNull()
    const shared = specWith([
      { id: 'R1', polygon: square(0, 0, 1000, 1000) },
      { id: 'R2', polygon: square(1000, 0, 2000, 1000) },
    ])
    expect(roomAt(shared, 1000, 500)).toBe('R1')
    expect(roomAt(shared, 1500, 500)).toBe('R2')
  })

  it('pointInPolygon classifies inside, boundary and outside', () => {
    const sq = square(0, 0, 10, 10)
    expect(pointInPolygon([5, 5], sq)).toBe('inside')
    expect(pointInPolygon([10, 3], sq)).toBe('boundary')
    expect(pointInPolygon([0, 0], sq)).toBe('boundary')
    expect(pointInPolygon([11, 5], sq)).toBe('outside')
  })

  it('roundHalfEven matches Python round', () => {
    expect(roundHalfEven(2.5)).toBe(2)
    expect(roundHalfEven(3.5)).toBe(4)
    expect(roundHalfEven(-2.5)).toBe(-2)
    expect(roundHalfEven(2.6)).toBe(3)
    expect(roundHalfEven(-2.6)).toBe(-3)
  })
})
