import { beforeEach, describe, expect, it, vi } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import { api, ApiError } from '../../api/client'
import type { Spec } from '../../types/spec'
import { useEditorStore } from '../store'
import { snapGuide } from './ReviewWorkspace'

vi.mock('../../api/client', async (orig) => ({ ...(await orig<typeof import('../../api/client')>()), api: { get: vi.fn(), post: vi.fn() } }))
const post = vi.mocked(api.post)
const st = () => useEditorStore.getState()

describe('snapGuide', () => {
  beforeEach(() => { st().load('p1', gtJson as unknown as Spec); post.mockReset() })

  it('adds the snapped wall', async () => {
    post.mockResolvedValue({ a: [0, 0], b: [3000, 0], thickness: 150 })
    await snapGuide('p1', [10, 90], [2990, 120])
    expect(post).toHaveBeenCalledWith('/api/projects/p1/snap', { a: [10, 90], b: [2990, 120] })
    expect(st().ops).toEqual([{ op: 'add_wall', a: [0, 0], b: [3000, 0], thickness: 150, kind: 'partition' }])
  })

  it('no double line nearby: a notice, no wall', async () => {
    post.mockRejectedValue(new ApiError(422, 'no_line', 'tidak ada garis ganda'))
    await snapGuide('p1', [0, 0], [3000, 0])
    expect(st().ops).toEqual([])
    expect(st().notice?.text).toBe('Tidak ada garis ganda di dekat garis ini')
  })
})
