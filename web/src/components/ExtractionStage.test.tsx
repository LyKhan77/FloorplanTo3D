import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { Run, Stage } from '../api/types'
import { ExtractionStage } from './ExtractionStage'

vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()), api: { get: vi.fn(), post: vi.fn() } }))
const get = vi.mocked(api.get)
const post = vi.mocked(api.post)

const stage = (n: number, over: Partial<Stage> = {}): Stage => ({
  n, name: ['input', 'preprocess', 'grid'][n] ?? 'x', status: 'succeeded', started_at: null, ended_at: null,
  duration_ms: 10, progress: null, metrics: {}, warnings: [], ...over })
const run = (stages: Stage[], status: Run['status'] = 'needs_attention'): Run => ({
  run_id: 'r1', project_id: 'p1', kind: 'full', from_stage: 0, version: null, spec_version_in: null, spec_version_out: null,
  status, stages, code_version: 't', blender_version: null, created_at: '', error: null })

function show(r: Run, n: number, message?: string) {
  render(<QueryClientProvider client={new QueryClient()}><ExtractionStage projectId="p1" run={r} n={n} message={message} /></QueryClientProvider>)
}

describe('ExtractionStage', () => {
  beforeEach(() => { get.mockReset(); post.mockReset() })

  it('stage 2 shows overlay, scale and warnings', () => {
    show(run([stage(0), stage(1), stage(2, { metrics: { mm_per_px: 25.8127, scale_source: 'grid_dimensions', axes_v: 6, axes_h: 3, residual_max_pct: 0.4 },
      warnings: ['dimensi total 28000 ≠ jumlah bagian'] })]), 2)
    expect(screen.getByText(/25\.813 mm\/px/)).toBeInTheDocument()
    expect(screen.getByText(/6 × 3 sumbu/)).toBeInTheDocument()
    expect(screen.getByAltText(/Sumbu grid/).getAttribute('src')).toMatch(/02_grid\/overlay\.png$/)
    expect(screen.getByText('dimensi total 28000 ≠ jumlah bagian')).toBeInTheDocument()
  })

  it('needs_attention offers manual scale', async () => {
    post.mockResolvedValue({ run_id: 'r2' })
    show(run([stage(0), stage(1), stage(2, { status: 'needs_attention' })]), 2, 'Skala tidak dapat ditentukan, isi skala manual')
    expect(screen.getByText('Skala tidak dapat ditentukan, isi skala manual')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Isi skala manual' }))
    const input = screen.getByLabelText('Skala manual (mm per px)')
    fireEvent.change(input, { target: { value: '0' } })
    fireEvent.click(screen.getByRole('button', { name: 'Jalankan' }))
    expect(post).not.toHaveBeenCalled()
    fireEvent.change(input, { target: { value: '26.5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Jalankan' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/projects/p1/runs',
      { kind: 'from_stage', from_stage: 2, params_override: { mm_per_px: 26.5 } }))
  })

  it('stage 0 lists final params', async () => {
    get.mockResolvedValue({ prompt: 'tinggi 4 m', params_final: { wall_height: 4000, mm_per_px: 25 } })
    show(run([stage(0)]), 0)
    expect(await screen.findByText('wall_height')).toBeInTheDocument()
    expect(screen.getByText('4000')).toBeInTheDocument()
    expect(screen.getByText('tinggi 4 m')).toBeInTheDocument()
    expect(get).toHaveBeenCalledWith('/api/projects/p1/runs/r1/artifacts/00_input/input.json')
  })

  it('stage 3 lists candidates and switches overlay', async () => {
    get.mockResolvedValue([
      { index: 0, params: { strategy: 'S2', sauvola_k: 0.2, t_min: 80, t_max: 450, l_fix: 0 }, counts: { walls: 161, doors: 38, columns: 30, stairs: 1 }, wall_len_m: 386.1, low_conf: 12, error: null },
      { index: 1, params: { strategy: 'S1', sauvola_k: 0.2, t_min: 80, t_max: 450, l_fix: 0 }, counts: { walls: 45, doors: 19, columns: 20, stairs: 1 }, wall_len_m: 49.2, low_conf: 3, error: null },
    ])
    show(run([stage(0), stage(1), stage(2), stage(3, { metrics: { candidates: 2 } })]), 3)
    expect(await screen.findByText('386.1')).toBeInTheDocument()
    expect(get).toHaveBeenCalledWith('/api/projects/p1/runs/r1/artifacts/03_extract/candidates.json')
    expect(screen.getByAltText(/Kandidat/).getAttribute('src')).toMatch(/03_extract\/candidates\/0\/overlay\.png$/)
    fireEvent.click(screen.getByText('S1'))
    expect(screen.getByAltText(/Kandidat/).getAttribute('src')).toMatch(/03_extract\/candidates\/1\/overlay\.png$/)
  })

  it('stage 3 candidates are keyboard-selectable radios; a failed candidate shows its error, not an overlay', async () => {
    get.mockResolvedValue([
      { index: 0, params: { strategy: 'S2', sauvola_k: 0.2, t_min: 80, t_max: 450, l_fix: 0 }, counts: { walls: 161, doors: 38, columns: 30, stairs: 1 }, wall_len_m: 386.1, low_conf: 12, error: null },
      { index: 1, params: { strategy: 'S1', sauvola_k: 0.2, t_min: 80, t_max: 450, l_fix: 0 }, counts: null, wall_len_m: 0, low_conf: 0, error: 'MemoryError: boom' },
    ])
    show(run([stage(0), stage(1), stage(2), stage(3, { metrics: { candidates: 2 } })]), 3)
    const radios = await screen.findAllByRole('radio')
    expect(radios).toHaveLength(2)
    expect(radios[0]).toBeChecked()
    fireEvent.click(radios[1])
    expect(radios[1]).toBeChecked()
    expect(screen.queryByAltText(/Kandidat/)).toBeNull()
    expect(screen.getAllByText('MemoryError: boom').length).toBeGreaterThan(0)
  })

  it('stage 1 shows the working page and preprocess facts', () => {
    show(run([stage(0), stage(1, { metrics: { deskew_deg: 0, upscale: 2, work_w: 3200, work_h: 1890 } })]), 1)
    expect(screen.getByRole('img').getAttribute('src')).toMatch(/01_preprocess\/page\.png$/)
    expect(screen.getByText(/3200 × 1890 px/)).toBeInTheDocument()
  })
})
