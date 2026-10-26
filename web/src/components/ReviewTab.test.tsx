import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { Run, Stage } from '../api/types'
import { ReviewTab } from './ReviewTab'

vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()), api: { get: vi.fn(), post: vi.fn() } }))
const get = vi.mocked(api.get)

const stage = (n: number, over: Partial<Stage> = {}): Stage => ({
  n, name: 'x', status: 'succeeded', started_at: null, ended_at: null, duration_ms: 1, progress: null, metrics: {}, warnings: [], ...over })
const run = (id: string, stages: Stage[]): Run => ({
  run_id: id, project_id: 'p1', kind: 'full', from_stage: 0, version: 1, spec_version_in: null, spec_version_out: 1,
  status: 'succeeded', stages, code_version: 't', blender_version: null, created_at: '', error: null })
const ISSUES = [{ code: 'V004', severity: 'warning', element_ids: ['W3'], message: 'open end' },
  { code: 'V012', severity: 'warning', element_ids: ['R2'], message: 'room without door' }]

function show(runs: Run[], url = '/projects/p1?tab=review') {
  render(<MemoryRouter initialEntries={[url]}><QueryClientProvider client={new QueryClient()}>
    <ReviewTab projectId="p1" runs={runs} /></QueryClientProvider></MemoryRouter>)
}

const extracted = run('r1', Array.from({ length: 11 }, (_, n) => stage(n, n === 5 ? { metrics: { version: 1 } } : n === 6 ? { status: 'skipped' } : {})))

describe('ReviewTab', () => {
  beforeEach(() => { get.mockReset(); get.mockResolvedValue(ISSUES) })

  it('shows numbered overlay with four layers and the issue table', async () => {
    show([run('r2', Array.from({ length: 11 }, (_, n) => stage(n, { status: n < 7 ? 'skipped' : 'succeeded' }))), extracted])
    expect(await screen.findByText('open end')).toBeInTheDocument()
    expect(get).toHaveBeenCalledWith('/api/projects/p1/runs/r1/artifacts/05_validate/issues.json')
    for (const label of ['Dinding', 'Pintu', 'Kolom', 'Ruang']) expect(screen.getByLabelText(label)).toBeInTheDocument()
    expect(screen.getByText(/Review Strata tersedia di M6/)).toBeInTheDocument()
  })

  it('focuses the issue row named in ?focus=', async () => {
    show([extracted], '/projects/p1?tab=review&focus=R2')
    const row = (await screen.findByText('room without door')).closest('tr')
    expect(row?.className).toMatch(/is-focused/)
    expect(screen.getByText('open end').closest('tr')?.className ?? '').not.toMatch(/is-focused/)
  })

  it('says so when no run has validation results', () => {
    show([run('r3', Array.from({ length: 11 }, (_, n) => stage(n, { status: 'pending' })))])
    expect(screen.getByText('Belum ada hasil validasi')).toBeInTheDocument()
  })
})
