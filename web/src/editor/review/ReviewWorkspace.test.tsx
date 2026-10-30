import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { useEditorStore } from '../store'
import { ReviewWorkspace } from './ReviewWorkspace'

const gt = gtJson as unknown as Spec
const st = () => useEditorStore.getState()

describe('ReviewWorkspace "Pintu"', () => {
  beforeEach(() => st().load('p1', gt))

  it('D picks the tool, and a click on a wall puts a door there', () => {
    const { container } = render(<ReviewWorkspace projectId="p1" rooms={[]} tasks={[]} backdrop={null} />)
    fireEvent.keyDown(window, { key: 'd' })
    expect(screen.getByRole('button', { name: 'Pintu' }).getAttribute('aria-pressed')).toBe('true')
    const w = gt.walls!.find((x) => x.id === 'W1')!  // y = 14450, x -2430..30440
    const svg = container.querySelector('svg')!
    fireEvent.pointerDown(svg, { clientX: 10000, clientY: -w.a[1], button: 0 })
    fireEvent.pointerUp(svg, { clientX: 10000, clientY: -w.a[1], button: 0 })
    expect(st().ops.at(-1)).toMatchObject({ op: 'add_opening', wall_id: 'W1', category: 'door', width: 900 })
  })

  it('a line dragged along a wall is the door, jamb to jamb', () => {
    const { container } = render(<ReviewWorkspace projectId="p1" rooms={[]} tasks={[]} backdrop={null} />)
    st().setTool('add-door')
    const svg = container.querySelector('svg')!, y = -14450  // W1, x -2430..30440
    fireEvent.pointerDown(svg, { clientX: 10000, clientY: y, button: 0 })
    fireEvent.pointerMove(svg, { clientX: 11200, clientY: y, button: 0 })
    fireEvent.pointerUp(svg, { clientX: 11200, clientY: y, button: 0 })
    expect(st().ops.at(-1)).toMatchObject({ op: 'add_opening', wall_id: 'W1', offset: 12430, width: 1200 })
  })

  it('a click off every wall only says so', () => {
    const { container } = render(<ReviewWorkspace projectId="p1" rooms={[]} tasks={[]} backdrop={null} />)
    st().setTool('add-door')
    const svg = container.querySelector('svg')!
    fireEvent.pointerUp(svg, { clientX: 90000, clientY: 0, button: 0 })
    expect(st().ops).toEqual([])
    expect(st().notice?.text).toMatch(/dinding/)
  })
})
