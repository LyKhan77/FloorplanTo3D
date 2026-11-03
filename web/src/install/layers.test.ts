import { describe, expect, it } from 'vitest'
import { cutaway, layerOf } from './layers'

describe('layerOf', () => {
  it('maps exported object names to viewer layers', () => {
    expect(layerOf('tray_power_T6')).toBe('Tray power')
    expect(layerOf('tray_data_T1_lip')).toBe('Tray data')
    expect(layerOf('hanger_T1_3')).toBe('Hanger')
    expect(layerOf('drop_RK1_T1')).toBe('Drop')
    expect(layerOf('rack_RK1')).toBe('Rack')
    expect(layerOf('obj_O2')).toBe('Perangkat')
    expect(layerOf('ceiling')).toBe('Plafon')
    expect(layerOf('raised_floor_panels')).toBe('Raised floor')
    expect(layerOf('wall_W1')).toBe('Dinding')
    expect(layerOf('frame_D3')).toBe('Dinding')
    expect(layerOf('room_R1')).toBeNull()
  })
})

describe('cutaway', () => {
  it('cuts walls, columns and doors above 1.2 m so trays show from outside (user: walls 4.5 m, trays at 3.6 m)', () => {
    const [plane] = cutaway(true)
    expect(plane.distanceToPoint({ x: 0, y: 1.0, z: 0 } as never)).toBeGreaterThan(0)  // kept
    expect(plane.distanceToPoint({ x: 0, y: 3.6, z: 0 } as never)).toBeLessThan(0)  // clipped
    expect(cutaway(false)).toEqual([])
  })
})

