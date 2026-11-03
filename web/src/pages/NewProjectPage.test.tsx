import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { NewProjectPage } from './NewProjectPage'

vi.mock('../api/client', async (orig) => ({
  ...(await orig<typeof import('../api/client')>()), api: { get: vi.fn(), post: vi.fn(), upload: vi.fn() },
}))
const get = vi.mocked(api.get)
const upload = vi.mocked(api.upload)
const thumb = 'data:image/png;base64,iVBORw0KGgo='

function show() {
  render(<MemoryRouter><QueryClientProvider client={new QueryClient()}><NewProjectPage /></QueryClientProvider></MemoryRouter>)
}

function pickFile(file: File) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  fireEvent.change(input, { target: { files: [file] } })
}

describe('NewProjectPage', () => {
  beforeEach(() => {
    get.mockReset(); upload.mockReset()
    get.mockResolvedValue([])
    upload.mockImplementation(async (path: string) => (path === '/api/pdf/pages'
      ? { page_count: 3, pages: [1, 2, 3].map((page) => ({ page, thumb })) }
      : { project_id: 'p1', run_id: 'r1' }) as never)
  })

  it('PDF shows page thumbnails and submits the picked page', async () => {
    show()
    pickFile(new File(['%PDF-'], 'ancol.pdf', { type: 'application/pdf' }))
    fireEvent.click(await screen.findByText('Hal. 2'))
    fireEvent.click(screen.getByRole('button', { name: 'Mulai pipeline' }))
    await waitFor(() => expect(upload).toHaveBeenCalledWith('/api/projects', expect.any(FormData)))
    const form = upload.mock.calls.find(([p]) => p === '/api/projects')![1] as FormData
    expect(form.get('page')).toBe('2')
  })

  it('an image sends no page and asks no thumbnails', async () => {
    show()
    pickFile(new File(['x'], 'plan.png', { type: 'image/png' }))
    fireEvent.click(screen.getByRole('button', { name: 'Mulai pipeline' }))
    await waitFor(() => expect(upload).toHaveBeenCalledWith('/api/projects', expect.any(FormData)))
    expect(upload).not.toHaveBeenCalledWith('/api/pdf/pages', expect.anything())
    expect((upload.mock.calls[0][1] as FormData).get('page')).toBeNull()
  })

  it('advanced params offer the door width instead of mm/px', () => {
    show()
    expect(screen.queryByLabelText(/mm per px/)).toBeNull()
    expect(screen.getByLabelText('Lebar pintu standar (mm)')).toBeInTheDocument()
  })
})
