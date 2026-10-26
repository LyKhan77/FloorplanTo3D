import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Template } from '../../api/types'
import type { Spec } from '../../types/spec'
import { applyOps } from '../ops/reducer'
import { useEditorStore } from '../store'
import { ObjectProps } from './ObjectProps'

const gt = gtJson as unknown as Spec
const [mx, my] = gt.rooms!.find((r) => r.name === 'R. MEETING')!.label_pos as [number, number]
const rack: Template = { id: 'rack', version: '1', name: 'Rack', category: 'rack', thumbnail_url: '', asset_url: '',
  dims: { w: 600, d: 1200, h: 2000 }, snap: { grid_mm: 600, align: 'edge' }, scale_mode: 'stretch',
  resizable: { w: false, d: { min: 1000, max: 1400, step: 100 }, h: false } }
const base = applyOps(gt, [{ op: 'add_object', template_id: 'rack', template_version: '1', position: [mx, my, 0], rotation: 0,
  dims: [600, 1200, 2000], label: 'A-01' }]).spec
const st = () => useEditorStore.getState()

function type(label: string, value: string) {
  const input = screen.getByLabelText(label)
  fireEvent.change(input, { target: { value } })
  fireEvent.blur(input)
}

describe('ObjectProps', () => {
  beforeEach(() => {
    st().load('p1', base)
    act(() => st().select(['O1']))
  })

  it('dims input clamps to resizable bounds and disables locked axes', () => {
    render(<ObjectProps o={st().view!.objects![0]} t={rack} />)
    expect(screen.getByLabelText('W (mm)')).toBeDisabled()
    expect(screen.getByLabelText('H (mm)')).toBeDisabled()
    type('D (mm)', '1349')
    expect(st().ops).toEqual([{ op: 'update_object', id: 'O1', dims: [600, 1300, 2000] }])
  })

  it('label empty sends null', () => {
    render(<ObjectProps o={st().view!.objects![0]} t={rack} />)
    type('Label', '')
    expect(st().ops).toEqual([{ op: 'update_object', id: 'O1', label: null }])
  })

  it('a locked object only offers unlocking', () => {
    const o = { ...st().view!.objects![0], locked: true }
    render(<ObjectProps o={o} t={rack} />)
    for (const label of ['X (mm)', 'Y (mm)', 'Z (mm)', 'Rotasi (°)', 'D (mm)', 'Label']) expect(screen.getByLabelText(label)).toBeDisabled()
  })

  it('position edit keeps the object inside a room', () => {
    render(<ObjectProps o={st().view!.objects![0]} t={rack} />)
    type('X (mm)', String(mx + 100))
    expect(st().ops).toEqual([{ op: 'update_object', id: 'O1', position: [mx + 100, my, 0] }])
    type('X (mm)', '-90000')
    expect(st().notice?.text).toBe('Objek harus tetap di dalam ruang')
    expect(st().ops).toHaveLength(1)
  })
})
