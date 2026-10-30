import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Run } from '../api/types'
import { RunPicker } from './RunPicker'

const run = (run_id: string, kind: Run['kind'], from_stage: number, status: Run['status'], created_at: string) =>
  ({ run_id, kind, from_stage, status, created_at }) as Run
const runs = [run('r3', 'regenerate', 7, 'succeeded', '2026-10-30T10:00:00+07:00'),
  run('r2', 'from_stage', 6, 'failed', '2026-10-30T09:30:00+07:00'), run('r1', 'full', 0, 'needs_review', '2026-10-30T09:00:00+07:00')]

describe('RunPicker', () => {
  it('lists every run, newest marked, and picks one', () => {
    const onChange = vi.fn()
    render(<RunPicker runs={runs} value="r3" onChange={onChange} />)
    fireEvent.click(screen.getByRole('combobox'))
    expect(screen.getByRole('option', { name: /Regenerate · Selesai · terbaru/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Dari tahap 6 · Gagal/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('option', { name: /Pipeline penuh · Perlu review/ }))
    expect(onChange).toHaveBeenCalledWith('r1')
  })
})
