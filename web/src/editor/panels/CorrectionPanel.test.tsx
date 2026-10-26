import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { applyOps } from '../ops/reducer'
import { useEditorStore } from '../store'
import { CorrectionPanel } from './CorrectionPanel'

const gt = gtJson as unknown as Spec
const st = () => useEditorStore.getState()
const w1 = gt.walls![0]
const door = gt.openings!.find((o) => o.category === 'door')!

function type(label: string, value: string) {
  const input = screen.getByLabelText(label)
  fireEvent.change(input, { target: { value } })
  fireEvent.blur(input)
}

describe('CorrectionPanel', () => {
  beforeEach(() => st().load('p1', gt))

  it('wall form sends only changed fields', () => {
    act(() => st().select([w1.id]))
    render(<CorrectionPanel />)
    type('a.x (mm)', String(w1.a[0] + 100))
    expect(st().ops).toEqual([{ op: 'move_wall', id: w1.id, a: [w1.a[0] + 100, w1.a[1]] }])
    type('Tebal (mm)', '200')
    expect(st().ops).toEqual([{ op: 'move_wall', id: w1.id, a: [w1.a[0] + 100, w1.a[1]], thickness: 200 }])
  })

  it('delete needs a reason', () => {
    act(() => st().select([w1.id]))
    render(<CorrectionPanel />)
    const del = screen.getByRole('button', { name: 'Hapus dinding' })
    expect(del).toBeDisabled()
    fireEvent.click(screen.getByRole('combobox', { name: /Alasan hapus/ }))
    fireEvent.click(screen.getByRole('option', { name: 'lainnya' }))
    expect(del).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Alasan lain'), { target: { value: 'bayangan' } })
    fireEvent.click(del)
    expect(st().ops).toEqual([{ op: 'delete_wall', id: w1.id, reason: 'bayangan' }])
  })

  it('stair flip swaps every flight', () => {
    const s1 = gt.stairs![0]
    act(() => st().select([s1.id]))
    render(<CorrectionPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Balik arah naik' }))
    expect(st().ops).toEqual([{ op: 'set_stair', id: s1.id, flights: s1.flights.map((f) => ({ ...f, start: f.end, end: f.start })) }])
  })

  it('door form edits width', () => {
    act(() => st().select([door.id]))
    render(<CorrectionPanel />)
    type('Lebar (mm)', String(door.width + 100))
    expect(st().ops).toEqual([{ op: 'set_door', id: door.id, width: door.width + 100 }])
  })

  it('merge two walls and add a wall without selection', () => {
    // two saved collinear pieces of W1
    act(() => {
      st().load('p1', applyOps(gt, [{ op: 'split_wall', id: w1.id, at_offset: 1000 }]).spec)
      st().select([w1.id, 'W78'])
    })
    const { unmount } = render(<CorrectionPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Gabung' }))
    expect(st().ops).toEqual([{ op: 'merge_walls', ids: [w1.id, 'W78'], reason: 'gabung dinding kolinear' }])
    unmount()
    act(() => { st().load('p1', gt) })
    render(<CorrectionPanel />)
    type('a.x (mm)', '0')
    type('a.y (mm)', '0')
    type('b.x (mm)', '3000')
    type('b.y (mm)', '0')
    fireEvent.click(screen.getByRole('button', { name: 'Tambah dinding' }))
    expect(st().ops).toEqual([{ op: 'add_wall', a: [0, 0], b: [3000, 0], thickness: gt.meta.defaults!.wall_thickness, kind: 'partition' }])
  })

  it('editing a wall created by split shows the save-first notice', () => {
    act(() => {
      st().apply({ op: 'split_wall', id: w1.id, at_offset: 1000 })
      st().select(['W78'])
    })
    render(<CorrectionPanel />)
    type('a.x (mm)', '0')
    expect(st().notice?.text).toContain('belum disimpan')
    expect(st().ops).toHaveLength(1)
  })
})
