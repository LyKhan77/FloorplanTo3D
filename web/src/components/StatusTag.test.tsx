import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { StageStatus } from '../api/types'
import { StatusTag } from './StatusTag'

describe('StatusTag', () => {
  it.each([
    ['running', 'Berjalan'],
    ['needs_attention', 'Perlu perhatian'],
    ['needs_review', 'Perlu review'],
    ['skipped', 'Dilewati'],
    ['queued', 'Menunggu'],
    ['failed', 'Gagal'],
  ])('%s shows an icon and text', (status, text) => {
    const { container } = render(<StatusTag status={status as StageStatus} />)
    expect(screen.getByText(text)).toBeInTheDocument()
    expect(container.querySelector('svg')).not.toBeNull()
  })

  it('shows the warning variant of succeeded', () => {
    render(<StatusTag status="succeeded" warning />)
    expect(screen.getByText('Selesai dengan peringatan')).toBeInTheDocument()
  })
})
