import { LinearFilter, LinearMipmapLinearFilter, type Material, type MeshStandardMaterial } from 'three'

const VIEWER_METALNESS = 0.4  // the viewer has no environment map: a 0.8 metal reads near black
const SLOT_SHADE = 0.12  // how dark a slot reads on the solid sheet

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
  // the slots (alpha 0) shade dark instead of being discarded: holes read close up, the sheet never vanishes, and
  // GLBs whose slot pixels are metal-coloured (built before the dark tile) show the perforation too
  m.onBeforeCompile = (shader) => {
    shader.fragmentShader = shader.fragmentShader.replace('#include <map_fragment>',
      '#include <map_fragment>\n\tdiffuseColor.rgb *= mix(SLOT_SHADE, 1.0, sampledDiffuseColor.a);\n\tdiffuseColor.a = 1.0;'
        .replace('SLOT_SHADE', SLOT_SHADE.toFixed(2)))
  }
  m.customProgramCacheKey = () => 'solid-perforation'
  m.needsUpdate = true
  return true
}
