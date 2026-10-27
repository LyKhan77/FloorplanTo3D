import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { Run, Stage } from '../api/types'
import { ReviewTab } from './ReviewTab'

vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()), api: { get: vi.fn(), post: vi.fn(), text: vi.fn() } }))
const get = vi.mocked(api.get)
const text = vi.mocked(api.text)

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

const extracted = run('r1', Array.from({ length: 11 }, (_, n) => stage(n, n === 5 ? { metrics: { version: 1 } }
  : n === 6 ? { status: 'skipped', metrics: { reason: 'strata_unavailable' } } : {})))
const reviewed = run('r1', Array.from({ length: 11 }, (_, n) => stage(n, n === 5 ? { metrics: { version: 1 } }
  : n === 6 ? { metrics: { reviewed: 2, accepted: 1, rejected: 1, score_before: 0.812, score_after: 0.825 } } : {})))
const DECISIONS = [
  { element: 'W2', task: 'T1', verdict: { id: 'W2', verdict: 'annotation' }, decision: 'accepted', reason: null,
    score_before: 0.812, score_after: 0.825, ops: [{ op: 'delete_wall', id: 'W2' }] },
  { element: 'W1', task: 'T1', verdict: { id: 'W1', verdict: 'annotation' }, decision: 'rejected', reason: 'score_drop',
    score_before: 0.825, score_after: 0.79, ops: [] },
]
const TRANSCRIPT = [
  JSON.stringify({ element: 'W2', task: 'T1', vote: 1, request: { messages_ref: 'crops/W2_v1.png' }, response: { raw: '{"verdict":"annotation"}', valid: true } }),
  '{not json',
  JSON.stringify({ element: 'W2', task: 'T1', vote: 2, request: { messages_ref: 'crops/W2_v2.png' }, response: { raw: '{"verdict":"annotation"} second', valid: true } }),
].join('\n')

describe('ReviewTab', () => {
  beforeEach(() => { get.mockReset(); get.mockResolvedValue(ISSUES) })

  it('shows numbered overlay with four layers and the issue table', async () => {
    show([run('r2', Array.from({ length: 11 }, (_, n) => stage(n, { status: n < 7 ? 'skipped' : 'succeeded' }))), extracted])
    expect(await screen.findByText('open end')).toBeInTheDocument()
    expect(get).toHaveBeenCalledWith('/api/projects/p1/runs/r1/artifacts/05_validate/issues.json')
    for (const label of ['Dinding', 'Pintu', 'Kolom', 'Ruang']) expect(screen.getByLabelText(label)).toBeInTheDocument()
    expect(screen.getByText('Review Strata dilewati: Strata tidak tersedia')).toBeInTheDocument()
  })

  it('focuses the issue row named in ?focus=', async () => {
    show([extracted], '/projects/p1?tab=review&focus=R2')
    const row = (await screen.findByText('room without door')).closest('tr')
    expect(row?.className).toMatch(/is-focused/)
    expect(screen.getByText('open end').closest('tr')?.className ?? '').not.toMatch(/is-focused/)
  })

  it('lists Strata decisions with tags and score delta', async () => {
    get.mockImplementation(async (path: string) => (path.endsWith('decisions.json') ? DECISIONS : ISSUES) as never)
    text.mockResolvedValue(TRANSCRIPT)
    show([reviewed])
    const row = (await screen.findByText('W2', { selector: 'td' })).closest('tr')!
    expect(row.textContent).toContain('accepted')
    expect(row.textContent).toContain('0.812 → 0.825')
    expect(screen.getByText('score_drop', { exact: false })).toBeInTheDocument()
    expect(get).toHaveBeenCalledWith('/api/projects/p1/runs/r1/artifacts/06_review/decisions.json')
  })

  it('row click shows crop, context and raw votes, skipping a broken transcript line', async () => {
    get.mockImplementation(async (path: string) => (path.endsWith('decisions.json') ? DECISIONS : ISSUES) as never)
    text.mockResolvedValue(TRANSCRIPT)
    show([reviewed])
    ;(await screen.findByText('W2', { selector: 'td' })).click()
    const crop = await screen.findByAltText('Crop W2')
    expect(crop.getAttribute('src')).toBe('/api/projects/p1/runs/r1/artifacts/06_review/crops/W2_v1.png')
    expect(screen.getByAltText('Konteks W2').getAttribute('src')).toBe('/api/projects/p1/runs/r1/artifacts/06_review/crops/W2_ctx.png')
    expect(screen.getByText(/second/)).toBeInTheDocument()
    expect(screen.getAllByLabelText(/Respons mentah/)).toHaveLength(2)
  })

  it('says so when no run has validation results', () => {
    show([run('r3', Array.from({ length: 11 }, (_, n) => stage(n, { status: 'pending' })))])
    expect(screen.getByText('Belum ada hasil validasi')).toBeInTheDocument()
  })
})
