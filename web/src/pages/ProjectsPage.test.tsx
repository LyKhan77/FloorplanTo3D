import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ProjectsPage } from './ProjectsPage'

const row = (id: string, fit: number | null, iou: number | null) => ({ project_id: id, name: id, floor: null, status: 'succeeded',
  active_stage: null, validator_score: null, iou, fit, head_version: 1, updated_at: '2026-10-30T10:00:00+07:00' })

vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()),
  api: { get: vi.fn(() => Promise.resolve({ items: [row('baru', 0.98, 0.67), row('lama', null, 0.67)], total: 2 })) } }))

describe('ProjectsPage', () => {
  it('the drawing fit column never shows an IoU (same numbers, other meaning)', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ProjectsPage /></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('0.98')).toBeInTheDocument()
    expect(screen.queryByText('0.67')).toBeNull()
  })
})
