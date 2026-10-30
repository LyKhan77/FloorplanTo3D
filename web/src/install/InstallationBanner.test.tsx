import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { ProjectDetail } from '../api/types'
import { InstallationBanner } from './InstallationBanner'

vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()),
  api: { get: vi.fn(), post: vi.fn(() => Promise.resolve({ meta: { version: 1 } })) } }))

const project = (over: Partial<ProjectDetail>) => ({ project_id: 'p1', params: {}, head: 3, outputs: [3], installation: null,
  summary: {}, ...over }) as unknown as ProjectDetail
const show = (p: ProjectDetail, onStarted = vi.fn()) =>
  render(<QueryClientProvider client={new QueryClient()}><InstallationBanner project={p} wallHeight={3000} onStarted={onStarted} /></QueryClientProvider>)

describe('InstallationBanner', () => {
  it('offers to start only when the layout has outputs and no installation exists', () => {
    show(project({ outputs: [] }))
    expect(screen.queryByRole('button', { name: 'Mulai instalasi' })).toBeNull()
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
