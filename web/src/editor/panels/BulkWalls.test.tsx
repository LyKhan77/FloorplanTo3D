import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { useEditorStore } from '../store'
import { CorrectionPanel } from './CorrectionPanel'

const gt = gtJson as unknown as Spec
const st = () => useEditorStore.getState()
const ids = () => st().view!.walls!.map((w) => w.id)

function deleteSelected(name: string) {
  render(<CorrectionPanel />)
  fireEvent.click(screen.getByRole('combobox', { name: /Alasan hapus/ }))
  fireEvent.click(screen.getByRole('option', { name: 'duplikat' }))
  fireEvent.click(screen.getByRole('button', { name }))
}

describe('BulkWalls', () => {
  beforeEach(() => st().load('p1', gt))

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
})
