import { describe, expect, it } from 'vitest'
import { buildProjectForm } from './params'

describe('buildProjectForm', () => {
  it('only sends filled advanced params', () => {
    const fd = buildProjectForm(new File(['x'], 'plan.jpeg'), { name: '', prompt: 'data hall', wallHeight: 4500, start: true })
    expect(fd.get('name')).toBe('plan')
    expect(fd.get('prompt')).toBe('data hall')
    expect(JSON.parse(fd.get('params') as string)).toEqual({ wall_height: 4500 })
    expect(fd.get('start')).toBe('true')
    expect((fd.get('file') as File).name).toBe('plan.jpeg')
  })

  it('maps every advanced field', () => {
    const fd = buildProjectForm(new File(['x'], 'a.png'), {
      name: 'A', wallHeight: 4500, doorHeight: 2400, wallThickness: 200, floorName: 'Lantai 1', siteType: 'data_hall',
      mmPerPx: 25.8, useStrata: false, start: false,
    })
    expect(JSON.parse(fd.get('params') as string)).toEqual({
      wall_height: 4500, door_height: 2400, wall_thickness: 200, floor_name: 'Lantai 1', site_type: 'data_hall',
      mm_per_px: 25.8, use_strata: false,
    })
  })

  it('rejects non-positive numbers', () => {
    expect(() => buildProjectForm(new File(['x'], 'a.png'), { wallHeight: -1, start: false })).toThrow(/wall_height/)
  })
})
