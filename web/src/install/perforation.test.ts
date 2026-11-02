import { describe, expect, it } from 'vitest'
import { LinearMipmapLinearFilter, MeshStandardMaterial, NearestFilter, Texture } from 'three'
import { solidPerforation } from './perforation'

describe('keepPerforationVisible', () => {
  it('draws an alpha-clipped sheet solid (the slots stay as dark texture), so a tray never vanishes (user report)', () => {
    const map = new Texture()
    map.minFilter = NearestFilter
    const mat = new MeshStandardMaterial({ map, alphaTest: 0.5, metalness: 0.8 })
    expect(solidPerforation(mat, 8)).toBe(true)
    expect([mat.alphaTest, mat.transparent, mat.alphaToCoverage]).toEqual([0, false, false])
    expect([map.minFilter, map.generateMipmaps, map.anisotropy]).toEqual([LinearMipmapLinearFilter, true, 8])
    expect(mat.metalness).toBeLessThanOrEqual(0.4)  // no environment map in the viewer: a metal would read black
  })

  it('leaves solid materials alone', () => {
    const plain = new MeshStandardMaterial({ color: '#7a7f85' })
    expect(solidPerforation(plain, 8)).toBe(false)
  })
})
