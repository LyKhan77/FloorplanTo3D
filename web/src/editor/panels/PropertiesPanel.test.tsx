import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { useEditorStore } from '../store'
import { LayersPanel } from './LayersPanel'
import { PropertiesPanel } from './PropertiesPanel'

const gt = gtJson as unknown as Spec
const st = () => useEditorStore.getState()
const meeting = gt.rooms!.find((r) => r.name === 'R. MEETING')!

function type(label: string, value: string) {
  const input = screen.getByLabelText(label)
  fireEvent.change(input, { target: { value } })
  fireEvent.blur(input)
}

describe('PropertiesPanel', () => {
  beforeEach(() => st().load('p1', gt))

  it('wall height rejects out-of-range input and resets with null', () => {
    act(() => st().select(['W1']))
    render(<PropertiesPanel />)
    type('Tinggi (mm)', '500')
    expect(screen.getByText('Isi 1000–12000 mm')).toBeInTheDocument()
    type('Tinggi (mm)', '')
    expect(st().ops).toEqual([])
    type('Tinggi (mm)', '4500')
    expect(st().ops).toEqual([{ op: 'set_wall_height', id: 'W1', height: 4500 }])
    fireEvent.click(screen.getByRole('button', { name: 'Ikut default' }))
    expect(st().ops).toEqual([{ op: 'set_wall_height', id: 'W1', height: null }])
  })

  it('multi-wall height emits one op per wall in one undo step', () => {
    act(() => st().select(['W1', 'W2']))
    render(<PropertiesPanel />)
    type('Tinggi (mm)', '5000')
    expect(st().ops).toHaveLength(2)
    expect(st().past).toHaveLength(1)
  })

  it('global default with override checkbox emits set_default then set_wall_height *', () => {
    render(<PropertiesPanel />)
    fireEvent.click(screen.getByLabelText('Terapkan juga ke dinding yang tingginya diatur khusus'))
    type('Tinggi dinding default (mm)', '4200')
    expect(st().ops).toEqual([
      { op: 'set_default', key: 'wall_height', value: 4200 },
      { op: 'set_wall_height', id: '*', height: null },
    ])
    expect(st().past).toHaveLength(1)
  })

  it('room height sets every bounding wall', () => {
    act(() => st().select([meeting.id]))
    render(<PropertiesPanel />)
    type('Tinggi dinding ruang ini (mm)', '3500')
    expect(st().ops).toHaveLength(meeting.bounding_walls!.length)
    expect(st().ops.every((o) => o.op === 'set_wall_height' && o.height === 3500)).toBe(true)
  })

  it('room type dropdown emits set_room_type and name emits rename_room', () => {
    act(() => st().select([meeting.id]))
    render(<PropertiesPanel />)
    type('Nama', 'RAPAT')
    fireEvent.click(screen.getByRole('combobox', { name: /Tipe/ }))
    fireEvent.click(screen.getByRole('option', { name: 'office' }))
    expect(st().ops).toEqual([
      { op: 'rename_room', id: meeting.id, name: 'RAPAT' },
      { op: 'set_room_type', id: meeting.id, type: 'office' },
    ])
  })

  it('shows read-only door info', () => {
    const door = gt.openings!.find((o) => o.category === 'door')!
    act(() => st().select([door.id]))
    render(<PropertiesPanel />)
    expect(screen.getByText(`Pintu ${door.id}`)).toBeInTheDocument()
  })
})

describe('LayersPanel', () => {
  beforeEach(() => st().load('p1', gt))

  it('layers panel toggles layers and cutaway', () => {
    render(<LayersPanel />)
    fireEvent.click(screen.getByLabelText('Grid 600'))
    expect(st().layers.grid).toBe(false)
    fireEvent.click(screen.getByLabelText('Cutaway'))
    expect(st().cutaway).toBe(3000)
    fireEvent.click(screen.getByLabelText('Cutaway'))
    expect(st().cutaway).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /R\. MEETING/ }))
    expect(st().selection).toEqual([meeting.id])
  })
})
