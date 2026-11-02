import { describe, expect, it } from 'vitest'
import { LinearMipmapLinearFilter, MeshStandardMaterial, NearestFilter, Texture } from 'three'
import { keepPerforationVisible } from './perforation'

describe('keepPerforationVisible', () => {
  it('mipmaps an alpha-clipped texture so the sheet stays solid from afar (the slots average out)', () => {
    const map = new Texture()
    map.minFilter = NearestFilter  // as exported for Blender's "Closest"
    map.magFilter = NearestFilter
    const mat = new MeshStandardMaterial({ map, alphaTest: 0.5 })
    expect(keepPerforationVisible(mat, 8)).toBe(true)
    expect([map.minFilter, map.generateMipmaps, map.anisotropy, mat.alphaToCoverage]).toEqual([LinearMipmapLinearFilter, true, 8, true])
  })

  it('leaves solid materials alone', () => {
    const plain = new MeshStandardMaterial({ color: '#7a7f85' })
    expect(keepPerforationVisible(plain, 8)).toBe(false)
  })
})
