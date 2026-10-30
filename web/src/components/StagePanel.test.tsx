import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { Run } from '../api/types'
import { StagePanel } from './StagePanel'

vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()),
  // chosen.json is an object; an array there crashed ValidateStage (an unhandled error that failed the suite)
  api: { get: vi.fn((url: string) => Promise.resolve(url.endsWith('chosen.json') ? null : [])), post: vi.fn(() => Promise.resolve({})) } }))

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
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false)
    fireEvent.click(screen.getByRole('button', { name: 'Batalkan review' }))
    expect(confirm).toHaveBeenCalled()
    expect(vi.mocked(api.post)).not.toHaveBeenCalled()  // dismissing is final: it asks first
    confirm.mockReturnValueOnce(true)
    fireEvent.click(screen.getByRole('button', { name: 'Batalkan review' }))
    await waitFor(() => expect(vi.mocked(api.post)).toHaveBeenCalledWith('/api/projects/p1/runs/r1/cancel'))
  })
})

describe('StagePanel verify (drawing fit)', () => {
  const run = { run_id: 'r1', project_id: 'p1', status: 'succeeded', kind: 'full', from_stage: 0, version: 3,
    stages: Array.from({ length: 11 }, (_, n) => stage(n, 'succeeded')) } as unknown as Run
  const show = (verify: object) => {
    vi.mocked(api.get).mockImplementation((url: string) => Promise.resolve(url.endsWith('verify.json') ? verify : []) as never)
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>
      <StagePanel projectId="p1" run={run} n={8} events={[]} onOpenEditor={vi.fn()} />
    </MemoryRouter></QueryClientProvider>)
  }
  const para = (re: RegExp) => (_: string, el: Element | null) => el?.tagName === 'P' && re.test(el.textContent ?? '')
  const base = { iou: 0.67, iou_threshold: 0.85, status: 'succeeded', warnings: [],
    glb_check: { pass: true, max_err_mm: 0.002, checked: 160 }, grid_check: { status: 'skipped' } }

  it('leads with the drawing fit and lists walls off the drawing; IoU is information', async () => {
    show({ ...base, fit_threshold: 0.9, drawing_fit: { fit: 0.98, walls_off: ['W192'], checked: 160, tolerance_mm: 50 } })
    expect(await screen.findByText('0.98')).toBeInTheDocument()
    expect(screen.getByText(/Kecocokan gambar · ambang 0.9/)).toBeInTheDocument()
    expect(screen.getByText(para(/tidak di atas garis gambar: W192/))).toBeInTheDocument()
    expect(screen.getByText(para(/IoU ke mask ekstraksi \(info\): 0\.67/))).toBeInTheDocument()
  })

  it('still shows an old verify.json without drawing fit', async () => {
    show(base)
    expect(await screen.findByText(para(/IoU ke mask ekstraksi \(info\): 0\.67/))).toBeInTheDocument()
    expect(screen.getByText(/Kecocokan gambar/)).toBeInTheDocument()
  })
})

describe('StagePanel skipped stage', () => {
  it('points to the run that ran it, and shows that run on click', () => {
    const skipped = { run_id: 'r3', project_id: 'p1', status: 'succeeded', kind: 'regenerate', from_stage: 7, version: 20,
      stages: Array.from({ length: 11 }, (_, n) => stage(n, n < 7 ? 'skipped' : 'succeeded')) } as unknown as Run
    const origin = { ...skipped, run_id: 'r1', created_at: '2026-10-30T09:00:00+07:00' } as Run
    const onShowRun = vi.fn()
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>
      <StagePanel projectId="p1" run={skipped} n={2} events={[]} onOpenEditor={vi.fn()} origin={origin} onShowRun={onShowRun} />
    </MemoryRouter></QueryClientProvider>)
    expect(screen.getByText((_, el) => el?.tagName === 'P' && /Hasilnya ada di run r1/.test(el.textContent ?? ''))).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Lihat run r1' }))
    expect(onShowRun).toHaveBeenCalledWith('r1')
  })
})
