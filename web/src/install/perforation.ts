import { LinearFilter, LinearMipmapLinearFilter, type Material, type MeshStandardMaterial } from 'three'

/** A perforated tray sheet is alpha-clipped at 0.5. Sampled without mipmaps (Blender "Closest" exports NEAREST), a
 *  distant pixel lands on a slot or on metal at random and the sheet vanishes; mipmapped, the slots average out (about
 *  0.78 alpha) and the sheet stays solid from afar while the holes show up close. */
export function keepPerforationVisible(material: Material, anisotropy: number): boolean {
  const m = material as MeshStandardMaterial
  if (!m.map || !(m.alphaTest > 0)) return false
  m.map.minFilter = LinearMipmapLinearFilter
  m.map.magFilter = LinearFilter
  m.map.generateMipmaps = true
  m.map.anisotropy = anisotropy
  m.map.needsUpdate = true
  m.alphaToCoverage = true  // smooth slot edges with MSAA instead of hard alpha-test stairs
  m.needsUpdate = true
  return true
}
