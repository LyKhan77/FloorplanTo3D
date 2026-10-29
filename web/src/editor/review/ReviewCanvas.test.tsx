import { fireEvent, render } from '@testing-library/react'
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
