import { describe, expect, it } from 'vitest'
import type { ApiEvent } from '../api/types'
import { filterEvents, formatLogLine } from './logs'

const log = (run: string, stage: number | null, level: string, msg: string, type = 'stage.log'): ApiEvent => ({
  seq: 1, ts: '2026-10-23T09:00:15.221+07:00', run_id: run, stage, type, level, msg, data: {},
})

describe('logs', () => {
  it('formats a log line', () => {
    expect(formatLogLine(log('r', 3, 'warn', 'hi'))).toEqual({ time: '09:00:15.221', stage: '[S3]', level: 'WARN', msg: 'hi' })
    expect(formatLogLine(log('r', null, 'info', '', 'run.finished')).stage).toBe('[--]')
  })

  it('describes lifecycle events without a message', () => {
    const e = { ...log('r', 7, 'info', '', 'stage.finished'), data: { status: 'succeeded', duration_ms: 4100 } }
    expect(formatLogLine(e).msg).toBe('stage.finished · succeeded · 4.1 s')
  })

  it('filters by run, stage, level and text', () => {
    const evs = [log('r1', 3, 'info', 'Candidate k3'), log('r1', 7, 'error', 'boom'), log('r2', 3, 'info', 'other')]
    expect(filterEvents(evs, { runId: 'r1', stages: [3], levels: ['info'], q: 'cand' }).map((e) => e.msg)).toEqual(['Candidate k3'])
    expect(filterEvents(evs, { runId: null, stages: [], levels: [], q: '' })).toHaveLength(3)
  })
})
