import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { EditorOp } from './ops/reducer'
import { useValidate } from './useValidate'

vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()), api: { post: vi.fn() } }))
const post = vi.mocked(api.post)
const base = { code: 'V001', severity: 'warning', element_ids: ['R1'], message: 'base' }
const fresh = { code: 'V008', severity: 'warning', element_ids: ['W1'], message: 'baru' }
const op = (h: number): EditorOp => ({ op: 'set_wall_height', id: 'W1', height: h })

describe('useValidate', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    post.mockReset()
    post.mockImplementation((_p, body) => Promise.resolve({
      score: 1, passed: true, issues: (body as { ops: EditorOp[] }).ops.length ? [base, fresh] : [base] }) as never)
  })
  afterEach(() => vi.useRealTimers())

  it('debounces to one request per 500 ms and marks new issues', async () => {
    const { result, rerender } = renderHook(({ ops }) => useValidate('p1', 4, ops), { initialProps: { ops: [] as EditorOp[] } })
    await act(async () => { await vi.advanceTimersByTimeAsync(10) })
    expect(post).toHaveBeenCalledTimes(1)
    expect(result.current.issues).toEqual([base])
    for (const h of [4000, 4100, 4200]) {
      rerender({ ops: [op(h)] })
      await act(async () => { await vi.advanceTimersByTimeAsync(100) })
    }
    expect(result.current.pending).toBe(true)
    await act(async () => { await vi.advanceTimersByTimeAsync(500) })
    expect(post).toHaveBeenCalledTimes(2)
    expect(post.mock.calls[1]).toEqual(['/api/projects/p1/specs/validate', { base_version: 4, ops: [op(4200)] }])
    expect(result.current.issues).toEqual([base, fresh])
    expect([...result.current.newIssues]).toEqual(['V008|W1'])
    expect(result.current.pending).toBe(false)
  })

  it('reports a bad op with its index', async () => {
    const { ApiError } = await vi.importActual<typeof import('../api/client')>('../api/client')
    post.mockImplementation((_p, body) => ((body as { ops: EditorOp[] }).ops.length
      ? Promise.reject(new ApiError(400, 'bad_op', 'unknown id W9', { index: 0 }))
      : Promise.resolve({ issues: [] })) as never)
    const ops = [op(4000)] // the store hands out a stable array
    const { result } = renderHook(() => useValidate('p1', 4, ops))
    await act(async () => { await vi.advanceTimersByTimeAsync(600) })
    expect(result.current.error).toBe('Op #1: unknown id W9')
  })

  it('a failed dry run keeps the last review tasks (M8 final review I4)', async () => {
    const { ApiError } = await vi.importActual<typeof import('../api/client')>('../api/client')
    const task = { id: 'gap:W1,W2', kind: 'gap', message: 'Celah', at: [0, 0], element_ids: ['W1', 'W2'], fix: {} }
    post.mockImplementation((_p, body) => ((body as { ops: EditorOp[] }).ops.length
      ? Promise.reject(new ApiError(500, 'internal', 'boom'))
      : Promise.resolve({ issues: [], rooms: [], tasks: [task] })) as never)
    const ops = [op(4000)]
    const { result } = renderHook(() => useValidate('p1', 4, ops))
    await act(async () => { await vi.advanceTimersByTimeAsync(600) })
    expect(result.current.tasks).toEqual([task])
  })
})
