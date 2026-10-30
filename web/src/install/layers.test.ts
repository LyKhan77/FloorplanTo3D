import { describe, expect, it } from 'vitest'
import { layerOf } from './layers'

describe('layerOf', () => {
  it('maps exported object names to viewer layers', () => {
    expect(layerOf('tray_power_T6')).toBe('Tray power')
    expect(layerOf('tray_data_T1_lip')).toBe('Tray data')
    expect(layerOf('hanger_T1_3')).toBe('Hanger')
    expect(layerOf('drop_RK1_T1')).toBe('Drop')
    expect(layerOf('rack_RK1')).toBe('Rack')
    expect(layerOf('ceiling')).toBe('Plafon')
    expect(layerOf('raised_floor_panels')).toBe('Raised floor')
    expect(layerOf('wall_W1')).toBeNull()
  })
})
