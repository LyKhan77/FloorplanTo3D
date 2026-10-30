import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../api/client'
import type { Installation } from '../types/installation'
import { InstallEditor } from './InstallEditor'
import { useInstallStore } from './store'

const base = { schema_version: '1.0', meta: { version: 1, layout_version: 1, default_mounting: 'overhead', id_seq: {} },
  cable_trays: [], objects: [], provenance_log: [] } as unknown as Installation
const other = { ...base, meta: { ...base.meta }, cable_trays: [{ id: 'T7', path: [[0, 0], [2000, 0]], tray_class: 'power', width: 400 }] } as unknown as Installation
let headP1 = base
vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()),
  api: { get: vi.fn((url: string) => Promise.resolve(url.includes('/p2/') ? other : url.endsWith('/HEAD') ? headP1 : [])), post: vi.fn() } }))
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

