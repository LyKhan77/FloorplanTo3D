import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import gtJson from '../../../benchmarks/gatsu/gt_spec.json'
import { api, ApiError } from '../api/client'
import type { Spec } from '../types/spec'
import { applyOps, type EditorOp } from './ops/reducer'
import { useEditorStore } from './store'
import { useSave } from './useSave'

vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()), api: { get: vi.fn(), post: vi.fn() } }))
const post = vi.mocked(api.post)
const get = vi.mocked(api.get)
const gt = { ...(gtJson as unknown as Spec), meta: { ...(gtJson as unknown as Spec).meta, version: 4 } }
const st = () => useEditorStore.getState()
const [px, py] = gt.rooms!.find((r) => r.name === 'R. MEETING')!.label_pos as [number, number]
const add: EditorOp = { op: 'add_object', template_id: 'r', template_version: '1', position: [px, py, 0], rotation: 0, dims: [600, 1200, 2000] }
const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>

function setup(regenerate = vi.fn()) {
  return { regenerate, ...renderHook(() => useSave('p1', regenerate), { wrapper }) }
}

describe('useSave', () => {
  beforeEach(() => {
    post.mockReset()
    get.mockReset()
    localStorage.clear()
    st().load('p1', gt)
    st().apply(add)
    st().apply({ op: 'set_door', id: 'D1', width: 1000 })
  })
  afterEach(() => localStorage.clear())

  it('201 clears ops and moves the base', async () => {
    const saved = { ...applyOps(gt, st().ops).spec, meta: { ...gt.meta, version: 5 } }
    post.mockResolvedValue({ version: 5, spec: saved, issues: [] })
    const { result, regenerate } = setup()
    await act(() => result.current.save())
    expect(post).toHaveBeenCalledWith('/api/projects/p1/specs', { base_version: 4, ops: [add, { op: 'set_door', id: 'D1', width: 1000 }],
      message: 'Edit editor: 2 op' })
    expect(st()).toMatchObject({ ops: [], baseVersion: 5 })
    expect(st().notice?.text).toBe('Tersimpan sebagai v5')
    expect(st().notice?.action?.label).toBe('Regenerate')
    expect(regenerate).not.toHaveBeenCalled()
    act(() => st().notice!.action!.onClick())
    expect(regenerate).toHaveBeenCalledWith(5)
  })

  it('a second save while the first is in flight sends nothing', async () => {
    let finish: (v: unknown) => void = () => {}
    post.mockImplementation(() => new Promise((r) => { finish = r }) as never)
    const { result } = setup()
    let first: Promise<void> = Promise.resolve()
    act(() => { first = result.current.save(); void result.current.save() })
    expect(post).toHaveBeenCalledTimes(1)
    await act(async () => { finish({ version: 5, spec: { ...gt, meta: { ...gt.meta, version: 5 } }, issues: [] }); await first })
  })

  it('422 keeps ops and shows issues', async () => {
    const issues = [{ code: 'V001', severity: 'error', element_ids: ['O1'], message: 'objek di luar ruang' }]
    post.mockRejectedValue(new ApiError(422, 'validation_failed', 'validation failed', { issues }))
    const { result } = setup()
    await act(() => result.current.save())
    expect(st().ops).toHaveLength(2)
    expect(st().saveIssues).toEqual(issues)
  })

  it('400 bad_op names the op', async () => {
    post.mockRejectedValue(new ApiError(400, 'bad_op', 'unknown id D1', { index: 1, op: 'set_door' }))
    const { result } = setup()
    await act(() => result.current.save())
    expect(st().notice?.text).toBe('Op #2 (set_door) ditolak: unknown id D1')
  })

  it('409 opens the rebase dialog with failed ops; cancel keeps everything; accept drops only failed ops', async () => {
    const other: EditorOp = { ...add, position: [px + 1234, py, 0] } as EditorOp
    const head = { ...applyOps(gt, [other, { op: 'delete_opening', id: 'D1', reason: 'x' }]).spec, meta: { ...gt.meta, version: 5 } }
    post.mockRejectedValue(new ApiError(409, 'spec_conflict', 'base 4 is not HEAD 5', { base: 4, head: 5 }))
    get.mockResolvedValue(head)
    const { result } = setup()
    await act(() => result.current.save())
    expect(get).toHaveBeenCalledWith('/api/projects/p1/specs/HEAD')
    expect(result.current.conflict?.failed.map((f) => f.index)).toEqual([1])
    const before = st().ops
    act(() => result.current.resolve(false))
    expect(result.current.conflict).toBeNull()
    expect(st().ops).toBe(before)
    await act(() => result.current.save())
    act(() => result.current.resolve(true))
    expect(st().baseVersion).toBe(5)
    expect(st().ops).toEqual([add])
    expect(st().view!.objects!.map((o) => o.id)).toEqual(['O1', 'O2'])
  })

  it('auto regenerate after save follows localStorage', async () => {
    localStorage.setItem('editor.autoRegenerate', '1')
    post.mockResolvedValue({ version: 5, spec: { ...gt, meta: { ...gt.meta, version: 5 } }, issues: [] })
    const { result, regenerate } = setup()
    await act(() => result.current.save())
    expect(regenerate).toHaveBeenCalledWith(5)
  })
})
