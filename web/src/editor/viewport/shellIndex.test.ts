import { Group, Mesh, Object3D } from 'three'
import { describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { applyOps } from '../ops/reducer'
import { buildShellIndex, hiddenIds, layerOf, specIdOf, wallScale } from './shellIndex'

const gt = gtJson as unknown as Spec

function node<T extends Object3D>(o: T, name: string, userData?: Record<string, unknown>): T {
  o.name = name
  if (userData) o.userData = userData
  return o
}

describe('shellIndex', () => {
  it('index maps spec ids including children of door empties', () => {
    const root = new Group()
    const door = node(new Group(), 'door_D1', { spec_id: 'D1', spec_type: 'door' })
    const frame = node(new Mesh(), 'frame_D1')
    const leaf = node(new Mesh(), 'leaf_D1_a')
    door.add(frame, leaf)
    const wall = node(new Mesh(), 'wall_W1', { spec_id: 'W1', spec_type: 'wall', height_mm: 3000 })
    root.add(door, wall)
    const idx = buildShellIndex(root)
    expect(idx.get('D1')).toEqual([door, frame, leaf])
    expect(idx.get('W1')).toEqual([wall])
    expect(specIdOf(leaf)).toBe('D1')
    expect(specIdOf(root)).toBeNull()
  })

  it('wallScale follows view height or default', () => {
    const v1 = applyOps(gt, [{ op: 'set_wall_height', id: 'W1', height: 4500 }]).spec
    expect(wallScale(v1, 'W1', 3000)).toBe(1.5)
    const v2 = applyOps(gt, [{ op: 'set_default', key: 'wall_height', value: 4000 }]).spec
    expect(v2.walls![0].height).toBeNull()
    expect(wallScale(v2, 'W1', 3000)).toBe(4000 / 3000)
    expect(wallScale(v2, 'W999', 3000)).toBe(1)
  })

  it('hiddenIds lists locally deleted shell elements', () => {
    const door = gt.openings!.find((o) => o.category === 'door')!
    const view = applyOps(gt, [
      { op: 'delete_wall', id: door.wall_id, reason: 'x' },
      { op: 'delete_stair', id: 'S1', reason: 'x' },
    ]).spec
    const hidden = hiddenIds(gt, view)
    expect(hidden.has(door.wall_id)).toBe(true)
    expect(hidden.has(door.id)).toBe(true)
    expect(hidden.has('S1')).toBe(true)
    expect(hidden.has('W1') && door.wall_id !== 'W1').toBe(false)
  })

  it('layerOf maps every spec_type in shell.glb', () => {
    expect(['wall', 'door', 'window', 'column', 'room', 'stair', 'slab'].map(layerOf))
      .toEqual(['walls', 'doors', 'doors', 'columns', 'always', 'always', 'always'])
  })
})
