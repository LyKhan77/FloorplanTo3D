import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { VersionsTab } from './VersionsTab'

vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()),
  api: {
    get: vi.fn(() => Promise.resolve([{ version: 20, source: 'editor', created_at: '2026-10-30T10:00:00+07:00', message: '', run_id: null, has_outputs: true }])),
    post: vi.fn((_: string, body: { force?: boolean }) => Promise.resolve(body.force ? { run_id: 'r2' } : { run_id: null, reused: true })),
  } }))

describe('VersionsTab regenerate', () => {
  it('says when outputs are reused and offers to rebuild anyway', async () => {
    render(<QueryClientProvider client={new QueryClient()}><VersionsTab projectId="p1" /></QueryClientProvider>)
    fireEvent.click(await screen.findByRole('button', { name: 'Regenerate versi ini' }))
    expect(await screen.findByText(/output v20 dipakai ulang/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Bangun ulang' }))
    await waitFor(() => expect(vi.mocked(api.post)).toHaveBeenLastCalledWith('/api/projects/p1/regenerate', { version: 20, force: true }))
  })
})
