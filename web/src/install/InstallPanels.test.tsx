import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import type { Installation } from '../types/installation'
import { InstallPanels } from './InstallPanels'
import { useInstallStore } from './store'

const base = { schema_version: '1.0', meta: { version: 1, layout_version: 1, default_mounting: 'overhead', id_seq: {} },
  cable_trays: [], objects: [], provenance_log: [] } as unknown as Installation
const lengths = { data: { horizontal: 5000, drops: 900, total: 5900 }, power: { horizontal: 0, drops: 0, total: 0 } }
const ist = () => useInstallStore.getState()

describe('InstallPanels', () => {
  beforeEach(() => ist().load(base))

  it('shows tray lengths per class in metres', () => {
    render(<InstallPanels validation={{ issues: [], drops: [], lengths, pending: false, error: null }} saveIssues={[]} />)
    const row = screen.getByRole('row', { name: /Data/ })
    expect(row.textContent).toContain('5.0')
    expect(row.textContent).toContain('5.9')
  })

  it('a tray is deleted only with a reason', () => {
    ist().apply({ op: 'add_tray', path: [[0, 0], [3000, 0]], tray_class: 'data' })
    ist().select(['T1'])
    render(<InstallPanels validation={{ issues: [], drops: [], lengths: null, pending: false, error: null }} saveIssues={[]} />)
    expect(screen.getByRole('button', { name: 'Hapus tray' })).toBeDisabled()
  })

  it('lists issues; their ids select the element', () => {
    ist().apply({ op: 'add_tray', path: [[0, 0], [3000, 0]], tray_class: 'data' })
    render(<InstallPanels validation={{ issues: [], drops: [], lengths: null, pending: false, error: null }}
      saveIssues={[{ code: 'I002', severity: 'error', element_ids: ['T1'], message: 'T1: tray underfloor butuh raised floor' }]} />)
    expect(screen.getByText(/butuh raised floor/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'T1' }))
    expect(ist().selection).toEqual(['T1'])
  })
})

describe('InstallPanels meta (review I4)', () => {
  beforeEach(() => ist().load(base))
  it('with nothing selected, the installation heights can be changed', () => {
    render(<InstallPanels validation={{ issues: [], drops: [], lengths: null, pending: false, error: null }} saveIssues={[]} />)
    const raised = screen.getByLabelText('Tinggi raised floor (mm, kosong = tidak ada)')
    fireEvent.change(raised, { target: { value: '600' } })
    fireEvent.blur(raised)
    expect(ist().ops.at(-1)).toEqual({ op: 'set_installation_meta', raised_floor_height: 600 })
    expect(ist().view!.meta.raised_floor_height).toBe(600)
  })
})


describe('InstallPanels device properties', () => {
  it('Z sets the height a device hangs at', () => {
    const o = { id: 'O7', template_id: 'fire-control-panel', template_version: '1.1.0', position: [3000, 100, 0], rotation: 0,
      dims: [500, 150, 700], room_id: null, label: null, locked: false }
    useInstallStore.getState().load({ schema_version: '1.0', meta: { version: 1, layout_version: 1, default_mounting: 'overhead', id_seq: {} },
      cable_trays: [], objects: [o], provenance_log: [] } as never, 'p1')
    useInstallStore.getState().select(['O7'])
    render(<InstallPanels validation={{ issues: [], drops: [], lengths: null, pending: false, error: null }} saveIssues={[]} />)
    const z = screen.getByLabelText('Z (mm)')
    fireEvent.change(z, { target: { value: '1400' } })
    fireEvent.blur(z)
    expect(useInstallStore.getState().ops.at(-1)).toMatchObject({ op: 'update_object', id: 'O7', position: [3000, 100, 1400] })
  })
})

describe('InstallPanels device ops the server accepts', () => {
  it('X and rotation fields carry a reason', () => {
    const o = { id: 'O8', template_id: 'ups-cabinet-generic', template_version: '1.1.0', position: [3000, 1000, 0], rotation: 0,
      dims: [1200, 800, 2000], room_id: null, label: null, locked: false }
    useInstallStore.getState().load({ schema_version: '1.0', meta: { version: 1, layout_version: 1, default_mounting: 'overhead', id_seq: {} },
      cable_trays: [], objects: [o], provenance_log: [] } as never, 'p1')
    useInstallStore.getState().select(['O8'])
    render(<InstallPanels validation={{ issues: [], drops: [], lengths: null, pending: false, error: null }} saveIssues={[]} />)
    for (const [label, v] of [['X (mm)', '3500'], ['Rotasi (°)', '90']]) {
      const f = screen.getByLabelText(label)
      fireEvent.change(f, { target: { value: v } })
      fireEvent.blur(f)
    }
    expect(useInstallStore.getState().ops.map((x) => (x as { reason?: string }).reason)).toEqual(['dipindah di editor', 'diputar di editor'])
  })
})

describe('InstallPanels turn buttons', () => {
  it('⟳ and ⟲ turn the device a quarter with a reason', () => {
    const o = { id: 'O9', template_id: 'ups-cabinet-generic', template_version: '1.1.0', position: [3000, 1000, 0], rotation: 0,
      dims: [1200, 800, 2000], room_id: null, label: null, locked: false }
    useInstallStore.getState().load({ schema_version: '1.0', meta: { version: 1, layout_version: 1, default_mounting: 'overhead', id_seq: {} },
      cable_trays: [], objects: [o], provenance_log: [] } as never, 'p1')
    useInstallStore.getState().select(['O9'])
    render(<InstallPanels validation={{ issues: [], drops: [], lengths: null, pending: false, error: null }} saveIssues={[]} />)
    fireEvent.click(screen.getByRole('button', { name: 'Putar 90° searah jarum jam' }))
    expect(useInstallStore.getState().ops.at(-1)).toMatchObject({ op: 'update_object', id: 'O9', rotation: 270, reason: 'diputar di editor' })
  })
})
