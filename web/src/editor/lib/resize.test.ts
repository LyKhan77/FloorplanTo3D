import { describe, expect, it } from 'vitest'
import type { Template } from '../../api/types'
import { clampDims, scaleOf } from './resize'

const t: Template = {
  id: 'rack', version: '1.0.0', name: 'Rack', category: 'rack', thumbnail_url: '', asset_url: '',
  dims: { w: 600, d: 1200, h: 2000 },
  resizable: { w: false, d: { min: 1000, max: 1200, step: 100 }, h: { min: 1800, max: 2400, step: 100 } },
  scale_mode: 'stretch', snap: { grid_mm: 600, align: 'edge' },
}

describe('resize', () => {
  it('clampDims clamps, steps from min, and keeps locked axes', () => {
    expect(clampDims([700, 1349, 1750], t)).toEqual([600, 1200, 1800])
    expect(clampDims([600, 1049, 2449], t)).toEqual([600, 1000, 2400])
    expect(clampDims([700, 1100, 2000], { ...t, scale_mode: 'fixed' })).toEqual([600, 1200, 2000])
  })

  it('scaleOf returns three-axis factors (w, h, d)', () => {
    expect(scaleOf([600, 1100, 2000], t)).toEqual([1, 1, 1100 / 1200])
  })
})
