import { describe, expect, it } from 'vitest'
import type { PlacedObject, Spec, Wall } from '../../types/spec'
import { idsInRect } from './rectPick'

const wall = (id: string, a: [number, number], b: [number, number]) => ({ id, a, b, thickness: 150, kind: 'partition' }) as Wall
const obj = (id: string, position: [number, number, number]) =>
  ({ id, position, dims: [100, 100, 100], template_id: 't', template_version: 1 }) as unknown as PlacedObject
const spec = (p: Partial<Spec>) => ({ meta: {}, ...p }) as unknown as Spec
const id2 = ([x, y]: [number, number, number]): [number, number] => [x, y]

describe('idsInRect', () => {
  const view = spec({ walls: [wall('W1', [0, 0], [100, 0]), wall('W2', [0, 0], [500, 0])], objects: [obj('O1', [50, 50, 0])] })

  it('picks walls with both ends inside and skips partial ones', () => {
    expect(idsInRect(view, { xa: -10, xb: 200, ya: -10, yb: 200 }, id2)).toEqual(['W1', 'O1'])
  })

  it('returns nothing for an empty rectangle', () => {
    expect(idsInRect(view, { xa: 1000, xb: 2000, ya: 1000, yb: 2000 }, id2)).toEqual([])
  })
})

const box = { xa: -10, xb: 200, ya: -10, yb: 200 }
const view2 = spec({ walls: [wall('W1', [0, 0], [100, 0])], objects: [obj('O1', [50, 50, 0])] })

describe('idsInRect with layers', () => {
  it('a hidden layer is not picked, so hiding objects gives a walls-only marquee', () => {
    expect(idsInRect(view2, box, id2, { walls: true, objects: false })).toEqual(['W1'])
    expect(idsInRect(view2, box, id2, { walls: false, objects: true })).toEqual(['O1'])
  })
})
