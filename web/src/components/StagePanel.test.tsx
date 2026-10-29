import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { Run } from '../api/types'
import { StagePanel } from './StagePanel'

vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()),
  api: { get: vi.fn(() => Promise.resolve([])), post: vi.fn(() => Promise.resolve({})) } }))

const stage = (n: number, status: string) => ({ n, name: `s${n}`, status, started_at: null, ended_at: null, duration_ms: null,
  progress: null, metrics: n === 5 ? { version: 1 } : {}, warnings: [] })

describe('StagePanel review pause (M11)', () => {
  it('offers to open or dismiss a paused review', async () => {
    const run = { run_id: 'r1', project_id: 'p1', status: 'needs_review', kind: 'full', from_stage: 0,
      stages: Array.from({ length: 11 }, (_, n) => stage(n, n <= 5 ? 'succeeded' : 'pending')) } as unknown as Run
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>
      <StagePanel projectId="p1" run={run} n={5} events={[]} onOpenEditor={vi.fn()} />
    </MemoryRouter></QueryClientProvider>)
    expect(screen.getByRole('button', { name: 'Buka review' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Batalkan review' }))
    await waitFor(() => expect(vi.mocked(api.post)).toHaveBeenCalledWith('/api/projects/p1/runs/r1/cancel'))
  })
})
