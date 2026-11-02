import { LinearFilter, LinearMipmapLinearFilter, type Material, type MeshStandardMaterial } from 'three'

const VIEWER_METALNESS = 0.4  // the viewer has no environment map: a 0.8 metal reads near black

/** A perforated tray sheet is alpha-clipped at 0.5 in the GLB (real holes in renders and other viewers). In the web
 *  viewer the alpha test discarded the whole sheet at distance (user report: only hangers and lips showed), so here the
 *  sheet is drawn solid: the slots are dark pixels in the tile and still read as perforation. */
export function solidPerforation(material: Material, anisotropy: number): boolean {
  const m = material as MeshStandardMaterial
  if (!m.map || !(m.alphaTest > 0)) return false
  m.alphaTest = 0
  m.transparent = false
  m.alphaToCoverage = false
  m.metalness = Math.min(m.metalness, VIEWER_METALNESS)
  m.map.minFilter = LinearMipmapLinearFilter
  m.map.magFilter = LinearFilter
  m.map.generateMipmaps = true
  m.map.anisotropy = anisotropy
  m.map.needsUpdate = true
  m.needsUpdate = true
  return true
}
