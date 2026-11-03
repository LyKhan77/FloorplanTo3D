import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { ProjectDetail } from '../api/types'
import { InstallationBanner } from './InstallationBanner'
import { useInstallStore } from './store'

vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()),
  api: { get: vi.fn(), post: vi.fn(() => Promise.resolve({ meta: { version: 1 } })) } }))

const project = (over: Partial<ProjectDetail>) => ({ project_id: 'p1', params: {}, head: 3, outputs: [3], installation: null,
  summary: {}, ...over }) as unknown as ProjectDetail
const show = (p: ProjectDetail, onStarted = vi.fn()) =>
  render(<QueryClientProvider client={new QueryClient()}><InstallationBanner project={p} wallHeight={3000} onStarted={onStarted} /></QueryClientProvider>)

describe('InstallationBanner', () => {
  it('offers to start whenever no installation exists, outputs or not (fit-out: devices live there)', () => {
    show(project({ outputs: [] }))
    expect(screen.getByRole('button', { name: 'Mulai instalasi' })).toBeInTheDocument()
    cleanup()
    show(project({ installation: { head: 1, layout_version: 3, layout_changed: false } }))
    expect(screen.queryByRole('button', { name: 'Mulai instalasi' })).toBeNull()
  })

  it('the start dialog posts heights and the default mounting', async () => {
    const onStarted = vi.fn()
    show(project({ params: { ceiling_height: 3200 } }), onStarted)
    fireEvent.click(screen.getByRole('button', { name: 'Mulai instalasi' }))
    expect((screen.getByLabelText('Tinggi plafon (mm)') as HTMLInputElement).value).toBe('3200')
    fireEvent.click(screen.getByLabelText('Ada raised floor'))
    fireEvent.change(screen.getByLabelText('Tinggi raised floor (mm)'), { target: { value: '600' } })
    fireEvent.click(screen.getByLabelText('Underfloor (di bawah raised floor)'))
    fireEvent.click(screen.getByRole('button', { name: 'Mulai' }))
    await waitFor(() => expect(vi.mocked(api.post)).toHaveBeenCalledWith('/api/projects/p1/installations/start',
      { ceiling_height: 3200, raised_floor_height: 600, default_mounting: 'underfloor' }))
    await waitFor(() => expect(onStarted).toHaveBeenCalled())
  })

  it('says when the layout changed and rebases', async () => {
    show(project({ head: 5, installation: { head: 2, layout_version: 3, layout_changed: true } }))
    expect(screen.getByText(/Layout berubah \(v3 → v5\)/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Rebase' }))
    await waitFor(() => expect(vi.mocked(api.post)).toHaveBeenCalledWith('/api/projects/p1/installations/rebase'))
  })
})

describe('InstallationBanner rebase safety (review I5, I6)', () => {
  it('Rebase waits until pending installation work is saved, and reports what it found', async () => {
    const changed = project({ head: 5, installation: { head: 2, layout_version: 3, layout_changed: true } })
    useInstallStore.getState().load({ meta: { version: 2, layout_version: 3 }, cable_trays: [], objects: [] } as never, 'p1')
    useInstallStore.getState().apply({ op: 'add_tray', path: [[0, 0], [3000, 0]], tray_class: 'data' })
    const { unmount } = show(changed)
    expect(screen.getByRole('button', { name: 'Rebase' })).toBeDisabled()
    unmount()
    useInstallStore.getState().load({ meta: { version: 2, layout_version: 3 }, cable_trays: [], objects: [] } as never, 'p1')
    vi.mocked(api.post).mockResolvedValueOnce({ version: 3, issues: [{ code: 'I008', severity: 'warning', element_ids: ['O1'], message: 'rack O1 tidak ada lagi' }] })
    show(changed)
    fireEvent.click(screen.getByRole('button', { name: 'Rebase' }))
    expect(await screen.findByText(/Rebase ke v5: 1 masalah/)).toBeInTheDocument()
  })
})

