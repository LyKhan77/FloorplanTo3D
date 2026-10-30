import { act, fireEvent, render } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { useEditorStore } from '../store'
import { ReviewCanvas } from './ReviewCanvas'

const gt = gtJson as unknown as Spec
const st = () => useEditorStore.getState()

describe('ReviewCanvas', () => {
  beforeEach(() => st().load('p1', gt))

  it('draws one line per wall and selects a wall on click', () => {
    const { container } = render(<ReviewCanvas rooms={gt.rooms!} tasks={[]} backdrop={null} />)
    const walls = container.querySelectorAll('line[data-wall]')
    expect(walls).toHaveLength(gt.walls!.length)
    fireEvent.click(walls[0])
    expect(st().selection).toEqual([walls[0].getAttribute('data-wall')])
  })

  it('draws stairs (clickable) and columns, and doors in a colour unlike the dark background', () => {
    const { container } = render(<ReviewCanvas rooms={gt.rooms!} tasks={[]} backdrop={null} />)
    const flights = container.querySelectorAll('[data-stair]')
    expect(flights).toHaveLength(gt.stairs!.flatMap((x) => x.flights).length)
    fireEvent.click(flights[0])
    expect(st().selection).toEqual([gt.stairs![0].id])
    expect(container.querySelectorAll('[data-column]')).toHaveLength(gt.columns!.length)
    const door = container.querySelector(`[data-opening="${gt.openings!.find((o) => o.category === 'door')!.id}"]`)!
    expect(door.getAttribute('stroke')).not.toBe('#0b0b0b')
  })

  it('a wheel over the canvas zooms it without scrolling the page', () => {
    const { container } = render(<ReviewCanvas rooms={gt.rooms!} tasks={[]} backdrop={null} />)
    const svg = container.querySelector('svg')!, before = svg.getAttribute('viewBox')
    const e = new WheelEvent('wheel', { deltaY: 100, bubbles: true, cancelable: true })
    act(() => { svg.dispatchEvent(e) })
    expect(e.defaultPrevented).toBe(true)
    expect(svg.getAttribute('viewBox')).not.toBe(before)
  })

  it('names a room named in the editor too (no OCR label position)', () => {
    const r = { ...gt.rooms![0], name: 'Battery Room', label_pos: null }
    const { container } = render(<ReviewCanvas rooms={[r]} tasks={[]} backdrop={null} />)
    expect([...container.querySelectorAll('text')].map((t) => t.textContent)).toContain('Battery Room')
  })

  it('marks the rooms of a leak task', () => {
    const r = gt.rooms![0]
    const leak = { id: `leak:${r.id}`, kind: 'leak' as const, message: 'x', at: [0, 0] as [number, number], element_ids: [r.id], fix: {} }
    const { container } = render(<ReviewCanvas rooms={gt.rooms!} tasks={[leak]} backdrop={null} />)
    expect(container.querySelectorAll('polygon.is-leak')).toHaveLength(1)
  })

  it('lays the page image under the plan', () => {
    const { container } = render(<ReviewCanvas rooms={[]} tasks={[]} backdrop={{ url: '/p.png', px_to_mm: [10, 0, 0, 0, -10, 6000] }} />)
    expect(container.querySelector('image')?.getAttribute('href')).toBe('/p.png')
  })
})

describe('ReviewCanvas pointer (M8 final review)', () => {
  beforeEach(() => st().load('p1', gt))

  it('a marquee can start on a room and selects the walls inside (I8)', () => {
    const { container } = render(<ReviewCanvas rooms={gt.rooms!} tasks={[]} backdrop={null} />)
    const room = container.querySelector('polygon')!
    const w = gt.walls![0]
    const [x0, x1] = [Math.min(w.a[0], w.b[0]) - 10, Math.max(w.a[0], w.b[0]) + 10]
    const [y0, y1] = [Math.min(w.a[1], w.b[1]) - 10, Math.max(w.a[1], w.b[1]) + 10]
    fireEvent.pointerDown(room, { button: 0, clientX: x0, clientY: -y1 })  // no CTM in jsdom: client px = SVG units
    fireEvent.pointerMove(room, { clientX: x1, clientY: -y0 })
    fireEvent.pointerUp(room, { clientX: x1, clientY: -y0 })
    fireEvent.click(room)
    expect(st().selection).toContain(w.id)
    expect(st().selection.every((id) => id.startsWith('W') || id.startsWith('O'))).toBe(true)
  })
})
