import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../api/client'
import type { Installation } from '../types/installation'
import { InstallEditor } from './InstallEditor'
vi.mock('./InstallViewer', () => ({ InstallViewer: ({ url }: { url: string }) => <p data-testid="viewer">{url}</p> }))
import { useInstallStore } from './store'

const base = { schema_version: '1.0', meta: { version: 1, layout_version: 1, default_mounting: 'overhead', id_seq: {} },
  cable_trays: [], objects: [], provenance_log: [] } as unknown as Installation
const other = { ...base, meta: { ...base.meta }, cable_trays: [{ id: 'T7', path: [[0, 0], [2000, 0]], tray_class: 'power', width: 400 }] } as unknown as Installation
let headP1 = base
vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()),
  api: { get: vi.fn((url: string) => Promise.resolve(url.endsWith('/HEAD') ? (url.includes('/p2/') ? other : headP1) : [])), post: vi.fn() } }))
const ui = (pid: string, qc = new QueryClient()) => <QueryClientProvider client={qc}><InstallEditor projectId={pid} backdrop={null} /></QueryClientProvider>

describe('InstallEditor save', () => {
  it('a refused save keeps the ops and lists the issues', async () => {
    vi.mocked(api.post).mockImplementation((url: string) => url.endsWith('/installations')
      ? Promise.reject(new ApiError(422, 'validation_failed', '1 validation error', { issues: [
        { code: 'I002', severity: 'error', element_ids: ['T1'], message: 'T1: tray underfloor butuh raised floor' }] }))
      : Promise.resolve({ issues: [], drops: [], lengths: null }) as never)
    render(<QueryClientProvider client={new QueryClient()}><InstallEditor projectId="p1" backdrop={null} /></QueryClientProvider>)
    await waitFor(() => expect(useInstallStore.getState().base?.meta.version).toBe(1))
    useInstallStore.getState().apply({ op: 'add_tray', path: [[0, 0], [3000, 0]], tray_class: 'data', mounting: 'underfloor' })
    fireEvent.click(await screen.findByRole('button', { name: 'Save' }))
    expect(await screen.findByText(/butuh raised floor/)).toBeInTheDocument()
    expect(useInstallStore.getState().ops).toHaveLength(1)
  })
})

describe('InstallEditor per project and conflicts', () => {
  it('another project loads its own installation, even with work pending on the first (review C1)', async () => {
    vi.mocked(api.post).mockResolvedValue({ issues: [], drops: [], lengths: null } as never)
    const qc = new QueryClient()
    const { rerender } = render(ui('p1', qc))
    await waitFor(() => expect(useInstallStore.getState().projectId).toBe('p1'))
    useInstallStore.getState().apply({ op: 'add_tray', path: [[0, 0], [3000, 0]], tray_class: 'data' })
    rerender(ui('p2', qc))
    await waitFor(() => expect(useInstallStore.getState().projectId).toBe('p2'))
    expect(useInstallStore.getState().view!.cable_trays!.map((t) => t.id)).toEqual(['T7'])
  })

  it('a save that lost a race replays the work on the newer version (review I6)', async () => {
    headP1 = base
    const newer = { ...base, meta: { ...base.meta, version: 2 } } as Installation
    vi.mocked(api.post).mockImplementation((url: string) => url.endsWith('/installations')
      ? Promise.reject(new ApiError(409, 'installation_conflict', 'base_version 1 is not HEAD (2)', { base: 1, head: 2 }))
      : Promise.resolve({ issues: [], drops: [], lengths: null }) as never)
    render(ui('p1'))
    await waitFor(() => expect(useInstallStore.getState().base?.meta.version).toBe(1))
    useInstallStore.getState().apply({ op: 'add_tray', path: [[0, 0], [3000, 0]], tray_class: 'data' })
    headP1 = newer
    fireEvent.click(await screen.findByRole('button', { name: 'Save' }))
    await waitFor(() => expect(useInstallStore.getState().base?.meta.version).toBe(2))
    expect(useInstallStore.getState().ops).toHaveLength(1)
    expect(useInstallStore.getState().notice?.text).toMatch(/diterapkan ulang/)
  })
})

describe('InstallEditor build and views (M12b)', () => {
  beforeEach(() => { headP1 = base; useInstallStore.getState().load(base, 'p1') })
  it('Build 3D waits for a save, then starts the installation run', async () => {
    headP1 = base
    vi.mocked(api.post).mockImplementation((url: string) => (url.endsWith('/build')
      ? Promise.resolve({ run_id: 'r9', status: 'queued' }) : Promise.resolve({ issues: [], drops: [], lengths: null })) as never)
    render(ui('p1'))
    await waitFor(() => expect(useInstallStore.getState().base?.meta.version).toBe(1))
    useInstallStore.getState().apply({ op: 'add_tray', path: [[0, 0], [3000, 0]], tray_class: 'data' })
    expect(await screen.findByRole('button', { name: 'Build 3D' })).toBeDisabled()
    useInstallStore.getState().load(base, 'p1')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Build 3D' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: 'Build 3D' }))
    await waitFor(() => expect(vi.mocked(api.post)).toHaveBeenCalledWith('/api/projects/p1/installations/build', {}))
  })

  it('a refused build lists the errors', async () => {
    vi.mocked(api.post).mockImplementation((url: string) => (url.endsWith('/build')
      ? Promise.reject(new ApiError(409, 'installation_invalid', 'instalasi masih punya error', { issues: [
        { code: 'I002', severity: 'error', element_ids: ['T1'], message: 'T1: tray underfloor butuh raised floor' }] }))
      : Promise.resolve({ issues: [], drops: [], lengths: null })) as never)
    render(ui('p1'))
    fireEvent.click(await screen.findByRole('button', { name: 'Build 3D' }))
    expect(await screen.findByText(/butuh raised floor/)).toBeInTheDocument()
  })

  it('the 3D view says when nothing is built yet', async () => {
    render(ui('p1'))
    fireEvent.click(await screen.findByRole('button', { name: '3D' }))
    expect(await screen.findByText(/Klik Build 3D setelah Save/)).toBeInTheDocument()
  })

  it('F fills the window in mode Instalasi too', async () => {
    const { container } = render(ui('p1'))
    await screen.findByRole('button', { name: 'Build 3D' })
    fireEvent.keyDown(window, { key: 'f' })
    expect(container.querySelector('.install-editor')!.classList.contains('editor--full')).toBe(true)
    expect(document.body.style.overflow).toBe('hidden')
    fireEvent.keyDown(window, { key: 'f' })
    expect(document.body.style.overflow).toBe('')
  })
})

describe('InstallEditor outputs (M12b review)', () => {
  beforeEach(() => { headP1 = base; useInstallStore.getState().load(base, 'p1') })
  const outs = [{ version: 1, built_at: 1700000000, files: ['installation_report.html', 'layout_installation.glb'] }]

  it('the viewer loads a rebuilt model (built_at in the URL) and the report opens in a tab', async () => {
    vi.mocked(api.get).mockImplementation((url: string) => Promise.resolve(url.endsWith('/HEAD') ? base : url.endsWith('/outputs') ? outs : []) as never)
    vi.mocked(api.post).mockResolvedValue({ issues: [], drops: [], lengths: null } as never)
    render(ui('p1'))
    const report = await screen.findByRole('link', { name: 'installation_report.html' })
    expect(report.getAttribute('target')).toBe('_blank')
    expect(report.hasAttribute('download')).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: '3D' }))
    expect((await screen.findByTestId('viewer')).textContent).toMatch(/layout_installation\.glb\?b=1700000000$/)
  })

  it('a build already running (editor reopened) shows progress and keeps Build 3D off', async () => {
    const running = { run_id: 'r9', kind: 'installation', status: 'running', stages: Array.from({ length: 11 }, (_, n) => ({ n, status: n === 7 ? 'running' : 'pending' })) }
    vi.mocked(api.get).mockImplementation((url: string) => Promise.resolve(url.endsWith('/HEAD') ? base : url.endsWith('/runs') ? [running]
      : url.includes('/runs/r9') ? running : []) as never)
    render(ui('p1'))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Build 3D' })).toBeDisabled())
  })
})


describe('InstallEditor on an older layout', () => {
  const project = { project_id: 'p1', head: 3, outputs: [3], params: {}, summary: {},
    installation: { head: 1, layout_version: 1, layout_changed: true } }
  beforeEach(() => {
    vi.mocked(api.get).mockImplementation(((url: string) => Promise.resolve(
      url.endsWith('/HEAD') ? base : url === '/api/projects/p1' ? project : [])) as never)
    vi.mocked(api.post).mockReset()
    vi.mocked(api.post).mockResolvedValue({ issues: [], drops: [], lengths: null, run_id: 'r1' } as never)
  })

  it('says the layout moved on and offers Rebase in the editor itself', async () => {
    render(ui('p1'))
    expect(await screen.findByText(/Layout berubah \(v1 → v3\)/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Rebase' })).toBeInTheDocument()
  })

  it('Build 3D asks first: the build would use the old layout', async () => {
    render(ui('p1'))
    await screen.findByText(/Layout berubah \(v1/)
    await waitFor(() => expect(useInstallStore.getState().base?.meta.version).toBe(1))
    fireEvent.click(screen.getByRole('button', { name: 'Build 3D' }))
    expect(vi.mocked(api.post).mock.calls.some(([u]) => String(u).endsWith('/build'))).toBe(false)
    expect(useInstallStore.getState().notice?.text).toMatch(/layout v1.*terbaru v3/)
    fireEvent.click(screen.getByRole('button', { name: 'Build 3D' }))
    await waitFor(() => expect(vi.mocked(api.post).mock.calls.some(([u]) => String(u).endsWith('/build'))).toBe(true))
  })
})
