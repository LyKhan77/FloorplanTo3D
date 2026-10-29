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

describe('ReviewWorkspace tools (M8 final review)', () => {
  beforeEach(() => st().load('p1', gt))

  it('the canvas handles follow the "Pasang pintu" choice (I2)', async () => {
    const { ReviewWorkspace } = await import('./ReviewWorkspace')
    const w = gt.walls!.find((x) => x.a[1] === x.b[1] && Math.abs(x.b[0] - x.a[0]) > 2000)!
    const dir = Math.sign(w.b[0] - w.a[0])
    const to: [number, number] = [w.b[0] + dir * 900, w.b[1]]
    const t: ReviewTask = { id: `gap:${w.id}:b`, kind: 'gap', message: 'Celah', at: to, element_ids: [w.id],
      fix: { a: w.b as [number, number], b: to, thickness: w.thickness, kind: w.kind, ends: [{ wall: w.id, end: 'b' }] } }
    act(() => { st().setReviewWithDoor(false); st().setActiveTask(t.id); st().setTool('close-gap') })
    const { container } = render(<ReviewWorkspace projectId="p1" rooms={[]} tasks={[t]} backdrop={null} />)
    act(() => { fireEvent.click(container.querySelector('[data-handle="0"]')!) })
    act(() => { fireEvent.click(container.querySelector('[data-handle="1"]')!) })
    expect(st().ops).toEqual([{ op: 'move_wall', id: w.id, b: to }])
  })

  it('the add-wall tool draws on the canvas: two clicks add a wall and chain (I7)', async () => {
    const { ReviewWorkspace } = await import('./ReviewWorkspace')
    act(() => { st().setTool('add-wall') })
    const { container } = render(<ReviewWorkspace projectId="p1" rooms={[]} tasks={[]} backdrop={null} />)
    const svg = container.querySelector('svg')!
    const click = (x: number, y: number) => {  // mm (x, y) -> SVG (x, -y); jsdom: client px = SVG units
      fireEvent.pointerDown(svg, { button: 0, clientX: x, clientY: -y })
      fireEvent.pointerUp(svg, { button: 0, clientX: x, clientY: -y })
    }
    act(() => { click(100000, 2000); click(103000, 2000) })
    expect(st().ops).toEqual([{ op: 'add_wall', a: [100000, 2000], b: [103000, 2000], thickness: 150, kind: 'partition' }])
    expect(st().wallDraft).toEqual({ a: [103000, 2000] })
    expect(container.querySelector('[aria-label="Garis bantu"]')).not.toBeNull()
  })
})
