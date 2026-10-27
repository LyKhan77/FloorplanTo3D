import { describe, expect, it } from 'vitest'
import type { Stage } from '../api/types'
import { parseTranscript, strataSummary, verdictText } from './strata'

const stage = (over: Partial<Stage>): Stage => ({
  n: 6, name: 'review', status: 'succeeded', started_at: null, ended_at: null, duration_ms: 1, progress: null,
  metrics: {}, warnings: [], ...over })

describe('strata helpers', () => {
  it('names the skip reason', () => {
    expect(strataSummary(stage({ status: 'skipped', metrics: { reason: 'strata_unavailable' } })))
      .toBe('Review Strata dilewati: Strata tidak tersedia')
    expect(strataSummary(stage({ status: 'skipped', metrics: { reason: 'disabled' } })))
      .toBe('Review Strata dilewati: tidak ada tugas Strata yang aktif')
  })

  it('summarises counts and score', () => {
    const s = stage({ metrics: { reviewed: 3, accepted: 1, rejected: 1, score_before: 0.812, score_after: 0.825 } })
    expect(strataSummary(s)).toBe('Diperiksa 3 · diterima 1 · ditolak 1 · skor 0.812 → 0.825')
    expect(strataSummary(stage({ status: 'pending' }), 'menunggu')).toBe('menunggu')
    const lost = stage({ metrics: { reviewed: 3, accepted: 1, rejected: 0, score_before: 0.8, score_after: 0.81, saved: false } })
    expect(strataSummary(lost)).toBe('Diperiksa 3 · diterima 1 · ditolak 0 · skor 0.800 → 0.810 · tidak disimpan')
  })

  it('renders verdicts without the id', () => {
    expect(verdictText({ id: 'W2', verdict: 'annotation' })).toBe('annotation')
    expect(verdictText({ id: 'D1', is_door: true, door_type: 'single_swing', hinge: 'end', swing: null }))
      .toBe('pintu · single_swing · end')
    expect(verdictText({ tool: 'delete_wall', arguments: { id: 'W3', reason: 'dim' } })).toBe('delete_wall W3')
    expect(verdictText(null)).toBe('—')
  })

  it('parses transcript lines and skips broken ones', () => {
    const text = '{"element":"W2","vote":1,"response":{"raw":"{}"}}\n{broken\n\n{"element":"W3","vote":1,"response":{"raw":"x"}}\n'
    expect(parseTranscript(text).map((l) => l.element)).toEqual(['W2', 'W3'])
  })
})
