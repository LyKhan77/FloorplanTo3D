import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
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
