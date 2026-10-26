import { describe, expect, it } from 'vitest'
import { fit, zoomAt } from './viewport'

describe('viewport', () => {
  it('zooms around the cursor', () => {
    const v = zoomAt({ scale: 1, x: 0, y: 0 }, 2, 100, 50)
    expect(v).toEqual({ scale: 2, x: -100, y: -50 }) // image point (100, 50) stays under the cursor
    expect(zoomAt({ scale: 19, x: 0, y: 0 }, 2, 0, 0).scale).toBe(20)
    expect(zoomAt({ scale: 0.15, x: 0, y: 0 }, 0.5, 0, 0).scale).toBe(0.1)
  })

  it('fits the image in the box', () => {
    expect(fit(1600, 945, 800, 800)).toEqual({ scale: 0.5, x: 0, y: (800 - 472.5) / 2 })
  })
})
