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
      doorLeafWidth: 850, useStrata: false, start: false,
    })
    expect(JSON.parse(fd.get('params') as string)).toEqual({
      wall_height: 4500, door_height: 2400, wall_thickness: 200, floor_name: 'Lantai 1', site_type: 'data_hall',
      door_leaf_width: 850, use_strata: false,
    })
  })

  it('sends the PDF page and the door width, never mm_per_px', () => {
    const fd = buildProjectForm(new File(['x'], 'a.pdf'), { page: 13, doorLeafWidth: 850, start: true })
    expect(fd.get('page')).toBe('13')
    expect(JSON.parse(fd.get('params') as string)).toEqual({ door_leaf_width: 850 })
    expect(buildProjectForm(new File(['x'], 'a.png'), { start: true }).get('page')).toBeNull()
  })

  it('rejects non-positive numbers', () => {
    expect(() => buildProjectForm(new File(['x'], 'a.png'), { wallHeight: -1, start: false })).toThrow(/wall_height/)
  })
})

describe('buildProjectForm profile', () => {
  it('new project form sends profile_id when a profile is chosen', () => {
    const file = new File(['x'], 'plan.jpeg')
    expect(buildProjectForm(file, { name: 'a', start: true, profileId: 'gatsu-ab12' }).get('profile_id')).toBe('gatsu-ab12')
    expect(buildProjectForm(file, { name: 'a', start: true }).get('profile_id')).toBeNull()
  })
})
