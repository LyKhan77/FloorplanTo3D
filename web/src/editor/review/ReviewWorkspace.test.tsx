import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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

describe('ReviewWorkspace "Perbaiki area"', () => {
  beforeEach(() => st().load('p1', gt))

  it('A picks the tool, and a drag marks the area', async () => {
    const { useAssistStore } = await import('../assist/store')
    useAssistStore.getState().close()
    const { container } = render(<ReviewWorkspace projectId="p1" rooms={[]} tasks={[]} backdrop={null} />)
    fireEvent.keyDown(window, { key: 'a' })
    expect(screen.getByRole('button', { name: 'Perbaiki area' }).getAttribute('aria-pressed')).toBe('true')
    const svg = container.querySelector('svg')!
    fireEvent.pointerDown(svg, { clientX: 1000, clientY: -2000, button: 0 })
    fireEvent.pointerMove(svg, { clientX: 4000, clientY: -6000, button: 0 })
    fireEvent.pointerUp(svg, { clientX: 4000, clientY: -6000, button: 0 })
    expect(useAssistStore.getState().box).toEqual([1000, 2000, 4000, 6000])
  })
})

describe('ReviewWorkspace "Perbaiki area" selection', () => {
  beforeEach(() => st().load('p1', gt))

  it('a click on a wall with tool A selects it and keeps the area', async () => {
    const { useAssistStore } = await import('../assist/store')
    useAssistStore.getState().open([0, 0, 5000, 5000])
    const { container } = render(<ReviewWorkspace projectId="p1" rooms={[]} tasks={[]} backdrop={null} />)
    st().setTool('assist')
    const line = container.querySelector('line[data-wall="W1"], [data-id="W1"]') ?? [...container.querySelectorAll('line')][0]
    const svg = container.querySelector('svg')!
    fireEvent.pointerDown(svg, { clientX: 10000, clientY: -14450, button: 0 })
    fireEvent.pointerUp(svg, { clientX: 10000, clientY: -14450, button: 0 })
    fireEvent.click(line)
    expect(st().selection.length).toBe(1)
    expect(useAssistStore.getState().box).toEqual([0, 0, 5000, 5000])
  })
})

describe('ReviewWorkspace drawn boxes', () => {
  beforeEach(() => st().load('p1', gt))

  it('a click with tool A asks for the drawn box and adds K1', async () => {
    const assist = await import('../assist/store')
    const stream = await import('../assist/stream')
    const spy = vi.spyOn(stream, 'drawnBox').mockResolvedValue({ center: [1000, 2000], size: [800, 1200], rotation: 0 })
    assist.useAssistStore.getState().close()
    assist.useAssistStore.getState().open([0, 0, 5000, 5000])
    const { container, findByText } = render(<ReviewWorkspace projectId="p1" rooms={[]} tasks={[]} backdrop={null} />)
    st().setTool('assist')
    const svg = container.querySelector('svg')!
    fireEvent.pointerDown(svg, { clientX: 1000, clientY: -2000, button: 0 })
    fireEvent.pointerUp(svg, { clientX: 1000, clientY: -2000, button: 0 })
    expect(spy).toHaveBeenCalledWith('p1', { at: [1000, 2000] })
    expect(await findByText('K1')).toBeTruthy()
    expect(assist.useAssistStore.getState().drawn).toEqual([{ id: 'K1', center: [1000, 2000], size: [800, 1200], rotation: 0 }])
    spy.mockRestore()
  })

  it('S draws a stair click by click, and Enter finishes it', () => {
    const { container } = render(<ReviewWorkspace projectId="p1" rooms={[]} tasks={[]} backdrop={null} />)
    const svg = container.querySelector('svg')!
    act(() => { fireEvent.keyDown(window, { key: 's' }) })
    for (const [x, y] of [[10000, -5000], [10000, -9000], [14000, -9000]]) {
      fireEvent.pointerDown(svg, { clientX: x, clientY: y, button: 0 })
      fireEvent.pointerUp(svg, { clientX: x, clientY: y, button: 0 })
    }
    expect(useEditorStore.getState().ops).toEqual([])
    act(() => { fireEvent.keyDown(window, { key: 'Enter' }) })
    const op = useEditorStore.getState().ops.at(-1) as { op: string; flights: unknown[]; landings: unknown[] }
    expect(op.op).toBe('add_stair')
    expect(op.flights).toHaveLength(2)
    expect(op.landings).toHaveLength(1)
  })

  it('a second click on the last point finishes too, and Esc drops the path', () => {
    const { container } = render(<ReviewWorkspace projectId="p1" rooms={[]} tasks={[]} backdrop={null} />)
    const svg = container.querySelector('svg')!
    const click = (x: number, y: number) => {
      fireEvent.pointerDown(svg, { clientX: x, clientY: y, button: 0 })
      fireEvent.pointerUp(svg, { clientX: x, clientY: y, button: 0 })
    }
    act(() => { fireEvent.keyDown(window, { key: 's' }) })
    click(10000, -5000); click(10000, -9000)
    act(() => { fireEvent.keyDown(window, { key: 'Escape' }) })
    expect(useEditorStore.getState().ops).toEqual([])
    act(() => { fireEvent.keyDown(window, { key: 's' }) })
    click(10000, -5000); click(10000, -9000); click(10000, -9000)
    expect((useEditorStore.getState().ops.at(-1) as { op: string }).op).toBe('add_stair')
  })
})
