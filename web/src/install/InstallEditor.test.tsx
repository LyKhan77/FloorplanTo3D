import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../api/client'
import type { Installation } from '../types/installation'
import { InstallEditor } from './InstallEditor'
import { useInstallStore } from './store'

const base = { schema_version: '1.0', meta: { version: 1, layout_version: 1, default_mounting: 'overhead', id_seq: {} },
  cable_trays: [], objects: [], provenance_log: [] } as unknown as Installation
vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()),
  api: { get: vi.fn((url: string) => Promise.resolve(url.endsWith('/HEAD') ? base : [])), post: vi.fn() } }))

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
