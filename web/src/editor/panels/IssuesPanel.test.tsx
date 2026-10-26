import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { applyOps } from '../ops/reducer'
import { useEditorStore, type Issue } from '../store'
import { IssuesPanel } from './IssuesPanel'

const gt = gtJson as unknown as Spec
const st = () => useEditorStore.getState()
const issue: Issue = { code: 'V008', severity: 'warning', element_ids: ['W1', 'W2'], message: 'Dinding menggantung' }

describe('IssuesPanel', () => {
  beforeEach(() => st().load('p1', gt))

  it('clicking an element id selects it', () => {
    st().setMissingTemplates(['O3'])
    render(<IssuesPanel issues={[issue]} newIssues={new Set(['V008|W1,W2'])} />)
    expect(screen.getByText('baru')).toBeInTheDocument()
    expect(screen.getByText('Dinding menggantung')).toBeInTheDocument()
    expect(screen.getByText(/Template tidak ada di registry/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'W2' }))
    expect(st().selection).toEqual(['W2'])
  })
})

describe('IssuesPanel collisions', () => {
  it('lists collisions as V017 warnings', () => {
    const [x, y] = gt.rooms!.find((r) => r.name === 'R. MEETING')!.label_pos as [number, number]
    const add = (dx: number) => ({ op: 'add_object' as const, template_id: 'r', template_version: '1',
      position: [x + dx, y, 0] as [number, number, number], rotation: 0, dims: [600, 1200, 2000] as [number, number, number] })
    st().load('p1', applyOps(gt, [add(0), add(300)]).spec)
    render(<IssuesPanel issues={[]} newIssues={new Set()} />)
    expect(screen.getByText('Tabrakan O1 ↔ O2')).toBeInTheDocument()
    expect(screen.getByText('V017')).toBeInTheDocument()
  })
})
