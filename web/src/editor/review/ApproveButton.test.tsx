import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import { api } from '../../api/client'
import type { Spec } from '../../types/spec'
import { useEditorStore } from '../store'
import { ApproveButton } from './ApproveButton'

vi.mock('../../api/client', async (orig) => ({ ...(await orig<typeof import('../../api/client')>()), api: { get: vi.fn(), post: vi.fn() } }))
const post = vi.mocked(api.post)
const st = () => useEditorStore.getState()
const gt = gtJson as unknown as Spec
const wrap = (ui: ReactNode) => <QueryClientProvider client={new QueryClient()}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>

function setup(save: () => Promise<void>) {
  render(wrap(<ApproveButton projectId="p1" runId="r1" tasksLeft={2} save={save} />))
  fireEvent.click(screen.getByRole('button', { name: 'Setujui & build 3D' }))
  fireEvent.click(screen.getByRole('button', { name: 'Setujui' }))
}

describe('ApproveButton', () => {
  beforeEach(() => { st().load('p1', gt); post.mockReset(); post.mockResolvedValue({ run_id: 'r2' }) })

  it('saves pending ops before continuing', async () => {
    const calls: string[] = []
    act(() => { st().apply({ op: 'delete_wall', id: 'W1', reason: 'uji' }) })
    const save = vi.fn(async () => { calls.push('save'); act(() => st().markSaved(gt)) })
    post.mockImplementation(async (path: string) => { calls.push(path); return { run_id: 'r2' } })
    setup(save)
    await waitFor(() => expect(calls).toEqual(['save', '/api/projects/p1/runs/r1/continue']))
  })

  it('with nothing to save it only continues', async () => {
    const save = vi.fn(async () => {})
    setup(save)
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/projects/p1/runs/r1/continue', { accept_low_score: false }))
    expect(save).not.toHaveBeenCalled()
  })

  it('a failed save stops before continuing', async () => {
    act(() => { st().apply({ op: 'delete_wall', id: 'W1', reason: 'uji' }) })
    const save = vi.fn(async () => {})  // ops stay: the save did not go through
    setup(save)
    await waitFor(() => expect(save).toHaveBeenCalled())
    expect(post).not.toHaveBeenCalled()
  })

  it('names the tasks still open', () => {
    render(wrap(<ApproveButton projectId="p1" runId="r1" tasksLeft={2} save={vi.fn()} />))
    fireEvent.click(screen.getByRole('button', { name: 'Setujui & build 3D' }))
    expect(screen.getByText(/2 tugas review belum selesai/)).toBeInTheDocument()
  })
})
