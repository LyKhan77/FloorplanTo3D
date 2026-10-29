import { describe, expect, it } from 'vitest'
import { imageMatrix, svgPoint } from './planTransform'

describe('planTransform', () => {
  it('imageMatrix places a page pixel at its mm (y flipped for SVG)', () => {
    const pxToMm = [12.92, 0, -5162.7, 0, -12.92, 15449.2]  // Gatsu, working image
    const m = imageMatrix(pxToMm).match(/matrix\(([^)]+)\)/)![1].split(',').map(Number)
    const [a, b, c, d, e, f] = m
    const [px, py] = [100, 200]
    const x = a * px + c * py + e, y = b * px + d * py + f  // SVG matrix(a b c d e f) applied to (px, py)
    expect(x).toBeCloseTo(12.92 * 100 - 5162.7, 6)
    expect(y).toBeCloseTo(-(-12.92 * 200 + 15449.2), 6)
  })

  it('svgPoint flips y', () => {
    expect(svgPoint([3000, 4000])).toEqual([3000, -4000])
  })
})
