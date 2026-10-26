import type { Template } from '../../api/types'
import { roundHalfEven } from './geom'

const AXES = ['w', 'd', 'h'] as const

/** dims are [w, d, h] mm; locked axes and scale_mode "fixed" keep the template's size. */
export function clampDims(dims: [number, number, number], t: Template): [number, number, number] {
  return AXES.map((k, i) => {
    const r = t.scale_mode === 'fixed' ? false : t.resizable?.[k]
    if (!r) return t.dims[k]
    const stepped = r.min + roundHalfEven((dims[i] - r.min) / r.step) * r.step
    return Math.min(r.max, Math.max(r.min, stepped))
  }) as [number, number, number]
}

/** Scale of the template asset in three axes: [w/W, h/H, d/D]. */
export function scaleOf(dims: [number, number, number], t: Template): [number, number, number] {
  return [dims[0] / t.dims.w, dims[2] / t.dims.h, dims[1] / t.dims.d]
}
