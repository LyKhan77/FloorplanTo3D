import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import gtJson from '../../../benchmarks/gatsu/gt_spec.json'
import type { OutputVersion } from '../api/types'
import type { Spec } from '../types/spec'
import { EditorTab } from './EditorTab'
import { useEditorStore } from './store'

const gt = gtJson as unknown as Spec
const routes: Record<string, unknown> = {}
vi.mock('../api/client', () => ({
  api: { get: vi.fn((path: string) => Promise.resolve(routes[path])), post: vi.fn() },
  outputsBase: (id: string, v: number) => `/api/projects/${id}/outputs/${v}`,
}))

// WebGL does not exist in jsdom; the viewport is verified in the browser (Task 15).
vi.mock('./viewport/Viewport', () => ({ Viewport: () => null }))

const spec = (version: number): Spec => ({ ...gt, meta: { ...gt.meta, version } })
const out = (version: number, files = ['shell.glb']): OutputVersion => ({ version, files: files.map((name) => ({ name, bytes: 1 })), renders: [] })

function setup(head: number, outputs: OutputVersion[]) {
  routes['/api/projects/p1/specs/HEAD'] = spec(head)
  routes['/api/projects/p1/outputs'] = outputs
  routes['/api/templates'] = []
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={qc}><EditorTab projectId="p1" run={null} /></QueryClientProvider>)
  return qc
}

const add = { op: 'add_object' as const, template_id: 'r', template_version: '1', position: [10880, 8470, 0] as [number, number, number],
  rotation: 0, dims: [600, 1200, 2000] as [number, number, number] }

describe('EditorTab', () => {
  beforeEach(() => useEditorStore.setState({ projectId: null, ops: [], base: null, baseVersion: null }))

  it('shows the stale shell banner', async () => {
    setup(4, [out(3), out(2)])
    expect(await screen.findByText('Shell dari v3; regenerate untuk memperbarui')).toBeInTheDocument()
  })

  it('shows an empty state without any shell', async () => {
    setup(4, [out(4, ['report.html'])])
    expect(await screen.findByText('Belum ada shell. Regenerate dulu.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Regenerate' }).length).toBeGreaterThan(0)
  })

  it('toolbar shows version and unsaved count', async () => {
    setup(4, [out(4)])
    await screen.findByText('v4')
    act(() => { useEditorStore.getState().applyMany([add, add, add]) })
    expect(screen.getByText('v4 (unsaved: 3)')).toBeInTheDocument()
    expect(screen.queryByText(/Shell dari/)).toBeNull()
  })

  it('warns before unload with unsaved ops', async () => {
    setup(4, [out(4)])
    await screen.findByText('v4')
    const fire = () => {
      const e = new Event('beforeunload', { cancelable: true })
      window.dispatchEvent(e)
      return e.defaultPrevented
    }
    expect(fire()).toBe(false)
    act(() => { useEditorStore.getState().apply(add) })
    expect(fire()).toBe(true)
  })

  it('store loads HEAD once per project', async () => {
    const qc = setup(4, [out(4)])
    await waitFor(() => expect(useEditorStore.getState().baseVersion).toBe(4))
    act(() => { useEditorStore.getState().apply(add) })
    routes['/api/projects/p1/specs/HEAD'] = spec(5)
    await act(() => qc.invalidateQueries())
    expect(useEditorStore.getState().ops).toHaveLength(1)
    expect(useEditorStore.getState().baseVersion).toBe(4)
  })
})
