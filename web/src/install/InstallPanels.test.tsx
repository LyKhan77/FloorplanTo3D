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
