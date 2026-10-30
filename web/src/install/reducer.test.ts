import { describe, expect, it } from 'vitest'
import type { Installation } from '../types/installation'
import { applyInstallOps, cleanPath } from './reducer'

const base = { schema_version: '1.0', meta: { version: 1, layout_version: 3, default_mounting: 'overhead', id_seq: {} },
  cable_trays: [], objects: [], provenance_log: [] } as unknown as Installation
const LINE: [number, number][] = [[0, 0], [5000, 0]]

describe('applyInstallOps', () => {
  it('adds trays with the class width and never reuses an id', () => {
    const { inst, failed } = applyInstallOps(base, [
      { op: 'add_tray', path: LINE, tray_class: 'data' },
      { op: 'add_tray', path: LINE, tray_class: 'power' },
      { op: 'delete_tray', id: 'T2', reason: 'x' },
      { op: 'add_tray', path: LINE, tray_class: 'power' },
    ])
    expect(failed).toEqual([])
    expect(inst.cable_trays!.map((t) => [t.id, t.width])).toEqual([['T1', 200], ['T3', 400]])
  })
  it('edits trays, objects and meta; an unknown id fails that op only', () => {
    const { inst, failed } = applyInstallOps(base, [
      { op: 'add_tray', path: LINE, tray_class: 'data' },
      { op: 'set_tray', id: 'T1', mounting: 'underfloor', elevation: -500 },
      { op: 'move_tray_path', id: 'T1', path: [[0, 0], [4000, 0]], reason: 'pita' },
      { op: 'add_object', template_id: 'rack-42u-600x1200', template_version: '1.0.0', position: [1000, 1000, 0], dims: [600, 1200, 2000] },
      { op: 'set_installation_meta', raised_floor_height: 600 },
      { op: 'delete_tray', id: 'T9', reason: 'x' },
    ])
    expect(failed.map((f) => f.index)).toEqual([5])
    expect(inst.cable_trays![0]).toMatchObject({ mounting: 'underfloor', elevation: -500, path: [[0, 0], [4000, 0]] })
    expect(inst.objects!.map((o) => o.id)).toEqual(['O1'])
    expect(inst.meta.raised_floor_height).toBe(600)
  })
})

describe('cleanPath', () => {
  it('drops points closer than 100 mm to the previous one (double clicks)', () => {
    expect(cleanPath([[0, 0], [30, 10], [3000, 0], [3000, 50], [3000, 2000]])).toEqual([[0, 0], [3000, 0], [3000, 2000]])
  })
})
