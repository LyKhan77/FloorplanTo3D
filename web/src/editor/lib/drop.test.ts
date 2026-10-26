import { describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Template } from '../../api/types'
import type { Spec } from '../../types/spec'
import { planDrop } from './drop'

const gt = gtJson as unknown as Spec
const rack: Template = { id: 'rack-42u-600x1200', version: '1.0.0', name: 'Rack', category: 'rack', thumbnail_url: '',
  asset_url: '', dims: { w: 600, d: 1200, h: 2000 }, snap: { grid_mm: 600, align: 'edge' } }

describe('planDrop', () => {
  it('planDrop snaps inside a room, rejects outside, warns on room type', () => {
    const r = planDrop(gt, rack, [10880, 8470], true)
    expect(r).toEqual({ op: { op: 'add_object', template_id: rack.id, template_version: '1.0.0', position: [11100, 8400, 0],
      rotation: 0, dims: [600, 1200, 2000] } })
    expect(planDrop(gt, rack, [10880, 8470], false)).toMatchObject({ op: { position: [10880, 8470, 0] } })
    expect(planDrop(gt, rack, [-50000, -50000], true)).toEqual({ error: 'Objek harus diletakkan di dalam ruang' })
    const typed: Spec = { ...gt, rooms: gt.rooms!.map((x) => (x.name === 'R. MEETING' ? { ...x, type: 'meeting' } : x)) }
    const warned = planDrop(typed, { ...rack, allowed_room_types: ['data_hall'] }, [10880, 8470], true)
    expect(warned).toMatchObject({ warning: 'Template ini tidak dianjurkan untuk tipe ruang meeting' })
    expect(planDrop(typed, { ...rack, allowed_room_types: ['meeting'] }, [10880, 8470], true)).not.toHaveProperty('warning')
  })
})
