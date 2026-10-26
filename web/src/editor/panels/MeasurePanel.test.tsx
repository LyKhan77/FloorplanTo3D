import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useEditorStore } from '../store'
import { MeasurePanel } from './MeasurePanel'

const st = () => useEditorStore.getState()

describe('MeasurePanel', () => {
  beforeEach(() => {
    st().clearMeasurements()
    st().addMeasurement({ id: 'm1', kind: 'distance', points: [[0, 0, 0], [3000, 4000, 0]], value: 5000, label: '5.000 m' })
    st().addMeasurement({ id: 'm2', kind: 'room-area', points: [], value: 67.48, label: '67.48 m²' })
  })

  it('lists measurements and removes them', () => {
    render(<MeasurePanel />)
    expect(screen.getByText('5.000 m')).toBeInTheDocument()
    expect(screen.getByText('67.48 m²')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: 'Hapus ukuran' })[0])
    expect(st().measurements.map((m) => m.id)).toEqual(['m2'])
    act(() => { fireEvent.click(screen.getByRole('button', { name: 'Hapus semua' })) })
    expect(st().measurements).toEqual([])
    expect(screen.getByText(/Belum ada ukuran/)).toBeInTheDocument()
  })
})
