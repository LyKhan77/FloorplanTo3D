import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { useEditorStore } from '../store'
import { CorrectionPanel } from './CorrectionPanel'

const gt = gtJson as unknown as Spec
const st = () => useEditorStore.getState()
const ids = () => st().view!.walls!.map((w) => w.id)

function spec(): Spec {
  const s = structuredClone(gt)
  const prov = { W1: ['cv', 0.3], W2: ['cv', 0.5], W3: ['cv', 0.8], W4: ['editor', 0.2] } as const
  for (const w of s.walls!) {
    const p = prov[w.id as keyof typeof prov]
    if (p) w.provenance = { source: p[0], confidence: p[1] }
  }
  return s
}

function deleteSelected(name: string) {
  render(<CorrectionPanel />)
  fireEvent.click(screen.getByRole('combobox', { name: /Alasan hapus/ }))
  fireEvent.click(screen.getByRole('option', { name: 'duplikat' }))
  fireEvent.click(screen.getByRole('button', { name }))
}

describe('BulkWalls', () => {
  beforeEach(() => st().load('p1', spec()))

  it('deletes every selected wall in one undo step', () => {
    act(() => st().select(['W1', 'W2']))
    deleteSelected('Hapus 2 dinding')
    expect(ids()).not.toContain('W1')
    expect(ids()).not.toContain('W2')
    act(() => st().undo())
    expect(ids()).toEqual(expect.arrayContaining(['W1', 'W2']))
  })

  it('warns how many doors go with the walls', () => {
    act(() => st().select(['W1', 'W40']))
    deleteSelected('Hapus 2 dinding')
    expect(st().notice?.text).toMatch('1 pintu ikut terhapus')
  })

  it('mixed selection (wall + room) offers no bulk delete', () => {
    act(() => st().select(['W1', 'W2', 'R1']))
    render(<CorrectionPanel />)
    expect(screen.queryByRole('button', { name: /Hapus \d+ dinding/ })).toBeNull()
  })

  it('selectDoubtfulWalls picks cv walls under 0.6 only', () => {
    expect(st().selectDoubtfulWalls()).toBe(2)
    expect(st().selection).toEqual(['W1', 'W2'])
  })

  it('empty selection offers the doubtful-walls button', () => {
    render(<CorrectionPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Pilih dinding ragu (< 0.6)' }))
    expect(st().selection).toEqual(['W1', 'W2'])
  })
})
