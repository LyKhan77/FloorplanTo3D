import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import gtJson from '../../../benchmarks/gatsu/gt_spec.json'
import type { Run, Stage } from '../api/types'
import type { Spec } from '../types/spec'
import { useEditorData } from './useEditorData'
import { useRegenerateFlow } from './useRegenerateFlow'

const routes: Record<string, unknown> = {}
vi.mock('../api/client', async (orig) => ({
  ...(await orig<typeof import('../api/client')>()),
  api: { get: vi.fn((p: string) => Promise.resolve(routes[p])), post: vi.fn(() => Promise.resolve({ run_id: 'r2' })) },
}))

const stage = (n: number, status: Stage['status'], progress: number | null = null): Stage => ({
  n, name: ['input', 'preprocess', 'grid', 'extract', 'rooms', 'validate', 'review', 'build', 'verify', 'report', 'publish'][n],
  status, progress, started_at: null, ended_at: null, duration_ms: null, metrics: {}, warnings: [] })
const run = (stages: Stage[], status: Run['status'] = 'running'): Run => ({
  run_id: 'r1', project_id: 'p1', kind: 'regenerate', from_stage: 7, version: 5, spec_version_in: 5, spec_version_out: null,
  status, stages, code_version: 't', blender_version: null, created_at: '', error: null })

describe('useRegenerateFlow', () => {
  it('progress follows stages 7-10 and the shell url switches when the new output appears', async () => {
    const skipped = [0, 1, 2, 3, 4, 5, 6].map((n) => stage(n, 'skipped'))
    const qc = new QueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    const r = run([...skipped, stage(7, 'succeeded'), stage(8, 'running', 0.5), stage(9, 'pending'), stage(10, 'pending')])
    const { result } = renderHook(() => useRegenerateFlow('p1', r), { wrapper })
    expect(result.current.progress).toBe(37.5)
    expect(result.current.stage).toBe('verify')
    expect(result.current.running).toBe(true)
    const idle = renderHook(() => useRegenerateFlow('p1', run(r.stages, 'succeeded')), { wrapper })
    expect(idle.result.current.progress).toBeNull()

    routes['/api/projects/p1/specs/HEAD'] = { ...(gtJson as unknown as Spec), meta: { ...(gtJson as unknown as Spec).meta, version: 5 } }
    routes['/api/projects/p1/outputs'] = [{ version: 4, files: [{ name: 'shell.glb', bytes: 1 }], renders: [] }]
    routes['/api/templates'] = []
    const data = renderHook(() => useEditorData('p1'), { wrapper })
    await waitFor(() => expect(data.result.current.shellUrl).toBe('/api/projects/p1/outputs/4/shell.glb'))
    expect(data.result.current.stale).toBe(true)
    routes['/api/projects/p1/outputs'] = [{ version: 5, files: [{ name: 'shell.glb', bytes: 1 }], renders: [] }]
    await act(() => qc.invalidateQueries({ queryKey: ['outputs', 'p1'] }))
    await waitFor(() => expect(data.result.current.shellUrl).toBe('/api/projects/p1/outputs/5/shell.glb'))
    expect(data.result.current.stale).toBe(false)
  })
})
