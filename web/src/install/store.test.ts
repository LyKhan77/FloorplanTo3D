import { beforeEach, describe, expect, it } from 'vitest'
import type { Installation } from '../types/installation'
import { useInstallStore } from './store'

const base = { schema_version: '1.0', meta: { version: 1, layout_version: 3, default_mounting: 'overhead', id_seq: {} },
  cable_trays: [], objects: [], provenance_log: [] } as unknown as Installation
const st = () => useInstallStore.getState()

describe('useInstallStore', () => {
  beforeEach(() => st().load(base))

  it('applies ops to the view and undoes them', () => {
    expect(st().apply({ op: 'add_tray', path: [[0, 0], [3000, 0]], tray_class: 'data' })).toBe(true)
    expect(st().view!.cable_trays!.map((t) => t.id)).toEqual(['T1'])
    st().undo()
    expect(st().view!.cable_trays).toEqual([])
    st().redo()
    expect(st().ops).toHaveLength(1)
  })

  it('refuses an op that fails, with a notice', () => {
    expect(st().apply({ op: 'delete_tray', id: 'T9', reason: 'x' })).toBe(false)
    expect(st().ops).toEqual([])
    expect(st().notice?.text).toMatch(/T9/)
  })

  it('switching tools drops a half-drawn tray', () => {
    st().setTool('tray')
    st().setTrayDraft([[0, 0], [1000, 0]])
    st().setTool('rack')
    expect(st().trayDraft).toEqual([])
  })

  it('a saved version becomes the new base with no pending ops', () => {
    st().apply({ op: 'add_tray', path: [[0, 0], [3000, 0]], tray_class: 'data' })
    st().load({ ...base, meta: { ...base.meta, version: 2 } })
    expect(st().ops).toEqual([])
    expect(st().base!.meta.version).toBe(2)
  })
})
