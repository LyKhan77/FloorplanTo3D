import type { Object3D } from 'three'
import type { Spec } from '../../types/spec'
import type { Layer } from '../store'


/** shell.glb node extras arrive as three userData: spec_id, spec_type, spec_version (+ height_mm on walls). */
export function specIdOf(obj: Object3D): string | null {
  for (let o: Object3D | null = obj; o; o = o.parent) {
    if (typeof o.userData?.spec_id === 'string') return o.userData.spec_id
  }
  return null
}

export function specTypeOf(obj: Object3D): string | null {
  for (let o: Object3D | null = obj; o; o = o.parent) {
    if (typeof o.userData?.spec_type === 'string') return o.userData.spec_type
  }
  return null
}

export function buildShellIndex(root: Object3D): Map<string, Object3D[]> {
  const idx = new Map<string, Object3D[]>()
  root.traverse((o) => {
    const id = specIdOf(o)
    if (id) idx.set(id, [...(idx.get(id) ?? []), o])
  })
  return idx
}

const LAYER: Record<string, Layer> = { wall: 'walls', column: 'columns', door: 'doors', window: 'doors' }
export const layerOf = (specType: string): Layer | 'always' => LAYER[specType] ?? 'always'

/** Effective wall height over the height baked into shell.glb. */
export function wallScale(view: Spec, wallId: string, bakedMm: number): number {
  const w = view.walls?.find((x) => x.id === wallId)
  if (!w || !bakedMm) return 1
  return (w.height ?? view.meta.defaults?.wall_height ?? bakedMm) / bakedMm
}

/** Shell elements deleted by local ops (walls cascade their openings). */
export function hiddenIds(base: Spec, view: Spec): Set<string> {
  const out = new Set<string>()
  for (const key of ['walls', 'openings', 'stairs'] as const) {
    const now = new Set((view[key] ?? []).map((e) => e.id))
    for (const e of base[key] ?? []) if (!now.has(e.id)) out.add(e.id)
  }
  return out
}

/** Layer visibility, local deletes and wall height preview on the loaded shell; true if any wall is rescaled. */
export function applyShellState(index: Map<string, Object3D[]>, base: Spec, view: Spec, layers: Record<Layer, boolean>): boolean {
  const hidden = hiddenIds(base, view)
  let scaled = false
  for (const [id, objs] of index) {
    for (const o of objs) {
      const type = specTypeOf(o) ?? ''
      const layer = layerOf(type)
      o.visible = (layer === 'always' || layers[layer]) && !hidden.has(id)
      if (type === 'wall' && typeof o.userData.height_mm === 'number') {
        o.scale.y = wallScale(view, id, o.userData.height_mm)
        scaled ||= Math.abs(o.scale.y - 1) > 1e-6
      }
    }
  }
  return scaled
}
