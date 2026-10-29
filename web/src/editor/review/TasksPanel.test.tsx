import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { ReviewTask } from '../../api/types'
import type { Spec } from '../../types/spec'
import { useEditorStore } from '../store'
import { TasksPanel } from './TasksPanel'

const gt = gtJson as unknown as Spec
const st = () => useEditorStore.getState()
const gap: ReviewTask = { id: 'gap:W1,W2', kind: 'gap', message: 'Celah 0.9 m di antara ujung dinding segaris', at: [0, 0],
  element_ids: ['W1', 'W2'], fix: { a: [0, 0], b: [900, 0], thickness: 120, kind: 'interior', ends: [] } }
const room: ReviewTask = { id: 'type:R1', kind: 'type', message: 'Tipe ruang belum pasti (R1)', at: [0, 0], element_ids: ['R1'], fix: {} }

describe('TasksPanel', () => {
  beforeEach(() => st().load('p1', gt))

  it('marks a task done when the validate response drops it', () => {
    const { rerender } = render(<TasksPanel projectId="p1" tasks={[gap, room]} />)
    expect(screen.getByText('0 / 2 selesai')).toBeInTheDocument()
    rerender(<TasksPanel projectId="p1" tasks={[room]} />)
    expect(screen.getByText('1 / 2 selesai')).toBeInTheDocument()
  })

  it('clicking a gap task switches to the close-gap tool', () => {
    render(<TasksPanel projectId="p1" tasks={[gap, room]} />)
    act(() => { fireEvent.click(screen.getByText(gap.message)) })
    expect(st().tool).toBe('close-gap')
    expect(st().activeTask).toBe(gap.id)
  })

  it('clicking a room-type task selects the room', () => {
    render(<TasksPanel projectId="p1" tasks={[gap, room]} />)
    act(() => { fireEvent.click(screen.getByText(room.message)) })
    expect(st().tool).toBe('select')
    expect(st().selection).toEqual(['R1'])
  })
})
