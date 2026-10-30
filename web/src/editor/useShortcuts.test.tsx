import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import gtJson from '../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../types/spec'
import { useInstallStore } from '../install/store'
import { useEditorStore } from './store'
import { useShortcuts } from './useShortcuts'

const gt = gtJson as unknown as Spec
const st = () => useEditorStore.getState()
const press = (key: string) => act(() => { window.dispatchEvent(new KeyboardEvent('keydown', { key })) })

describe('useShortcuts', () => {
  beforeEach(() => st().load('p-1', gt))

  it.each(['Delete', 'Backspace'])('%s deletes the selected walls, and undo brings them back', (key) => {
    renderHook(() => useShortcuts([], () => {}))
    const [w1, w2] = gt.walls!
    st().select([w1.id, w2.id])
    press(key)
    expect(st().view!.walls!.map((w) => w.id)).not.toContain(w1.id)
    expect(st().view!.walls!.map((w) => w.id)).not.toContain(w2.id)
    expect(st().ops.at(-1)).toEqual({ op: 'delete_wall', id: w2.id, reason: 'tombol Delete' })
    expect(st().selection).toEqual([])
    st().undo()
    expect(st().view!.walls).toHaveLength(gt.walls!.length)
  })
})

describe('useShortcuts and mode Instalasi (review I7)', () => {
  it('keeps working for the layout unless the installation editor is on screen', () => {
    useEditorStore.getState().load('p-1', gt)
    useInstallStore.getState().setActive(true)  // left over from another project; no installation editor mounted
    renderHook(() => useShortcuts([], () => {}))
    useEditorStore.getState().select([gt.walls![0].id])
    act(() => { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete' })) })
    expect(useEditorStore.getState().view!.walls!.map((w) => w.id)).not.toContain(gt.walls![0].id)
    useInstallStore.getState().setActive(false)
  })
})

