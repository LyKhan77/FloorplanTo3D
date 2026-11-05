import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import { api, ApiError } from '../../api/client'
import type { Room, Spec } from '../../types/spec'
import { useEditorStore } from '../store'
import { PropertiesPanel } from './PropertiesPanel'

vi.mock('../../api/client', async (orig) => ({ ...(await orig<typeof import('../../api/client')>()), api: { post: vi.fn() } }))
const post = vi.mocked(api.post)
const gt = gtJson as unknown as Spec
const st = () => useEditorStore.getState()
const [a, b] = [gt.rooms![0], gt.rooms![1]]
const wall = gt.walls![0]
const mid = [(wall.a[0] + wall.b[0]) / 2, (wall.a[1] + wall.b[1]) / 2]
const around = { ...a, polygon: [[mid[0] - 99, mid[1] - 99], [mid[0] + 99, mid[1] - 99], [mid[0] + 99, mid[1] + 99], [mid[0] - 99, mid[1] + 99]],
  area_m2: 123.45 } as Room

describe('merging rooms in Properties', () => {
  beforeEach(() => {
    post.mockReset()
    st().load('p1', gt)
  })

  it('Gabung ruangan asks for a plan and applies it', async () => {
    post.mockResolvedValue({ ops: [{ op: 'set_wall_divides', id: wall.id, divides: false }] })
    act(() => st().select([a.id, b.id]))
    render(<PropertiesPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Gabung ruangan' }))
    await waitFor(() => expect(st().ops).toHaveLength(1))
    expect(post).toHaveBeenCalledWith('/api/projects/p1/specs/merge-plan',
      { base_version: gt.meta.version, ops: [], room_ids: [a.id, b.id] })
    expect(st().selection).toEqual([])
  })

  it('a refusal shows its reason and applies nothing', async () => {
    post.mockRejectedValue(new ApiError(400, 'merge_refused', 'Ruangan tidak berbagi dinding'))
    act(() => st().select([a.id, b.id]))
    render(<PropertiesPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Gabung ruangan' }))
    await waitFor(() => expect(st().notice?.text).toBe('Ruangan tidak berbagi dinding'))
    expect(st().ops).toEqual([])
  })

  it('a plan for ops that changed meanwhile is dropped', async () => {
    let answer: (v: unknown) => void = () => {}
    post.mockReturnValue(new Promise((done) => { answer = done }))
    act(() => st().select([a.id, b.id]))
    render(<PropertiesPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Gabung ruangan' }))
    act(() => { st().apply({ op: 'rename_room', id: a.id, name: 'X' }) })
    await act(async () => answer({ ops: [{ op: 'set_wall_divides', id: wall.id, divides: false }] }))
    expect(st().ops).toHaveLength(1)
    expect(st().notice?.kind).toBe('warning')
  })

  it('Pisahkan ruangan shows only on a room holding a wall that does not divide', () => {
    act(() => st().select([a.id]))
    const { rerender } = render(<PropertiesPanel rooms={[around]} />)
    expect(screen.queryByRole('button', { name: 'Pisahkan ruangan' })).toBeNull()
    act(() => { st().apply({ op: 'set_wall_divides', id: wall.id, divides: false }) })
    rerender(<PropertiesPanel rooms={[around]} />)
    expect(screen.getByRole('button', { name: 'Pisahkan ruangan' })).toBeInTheDocument()
  })

  it('a box with rooms and walls keeps both sets of actions', () => {
    act(() => st().select([wall.id, gt.walls![1].id, a.id, b.id]))
    render(<PropertiesPanel />)
    expect(screen.getByRole('button', { name: 'Gabung ruangan' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Gabung' })).toBeInTheDocument()
  })

  it('one room caught with walls leaves the wall actions as they were', () => {
    act(() => st().select([wall.id, gt.walls![1].id, a.id]))
    render(<PropertiesPanel />)
    expect(screen.queryByRole('button', { name: 'Gabung ruangan' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Gabung' })).toBeInTheDocument()
  })

  it('a known room shows what the dry run says about it', () => {
    act(() => st().select([a.id]))
    render(<PropertiesPanel rooms={[around]} />)
    expect(screen.getByText(/123,45|123\.45/)).toBeInTheDocument()
  })
})
