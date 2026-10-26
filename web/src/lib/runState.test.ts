import { describe, expect, it } from 'vitest'
import type { ApiEvent, Run } from '../api/types'
import { applyEvent, emptyRun, stageLabel, withEvents } from './runState'

function ev(type: string, stage: number | null, data: Record<string, unknown> = {}): ApiEvent {
  return { seq: 1, ts: '2026-10-26T10:00:00.000+07:00', run_id: 'r1', stage, type, level: 'info', msg: '', data }
}

describe('applyEvent', () => {
  it('applies stage events in order', () => {
    let run: Run = emptyRun('r1', 'regenerate')
    run = applyEvent(run, ev('stage.started', 7))
    run = applyEvent(run, ev('stage.progress', 7, { percent: 60, msg: 'built' }))
    expect(run.stages[7]).toMatchObject({ status: 'running', progress: 60 })
    run = applyEvent(run, ev('stage.finished', 7, { status: 'succeeded', duration_ms: 4100 }))
    run = applyEvent(run, ev('run.finished', null, { status: 'succeeded' }))
    expect([run.stages[7].status, run.stages[7].duration_ms, run.status]).toEqual(['succeeded', 4100, 'succeeded'])
  })

  it('ignores events of another run', () => {
    expect(applyEvent(emptyRun('r1', 'full'), { ...ev('stage.started', 3), run_id: 'r2' }).stages[3].status).toBe('pending')
  })

  it('labels stages in Indonesian', () => {
    expect([stageLabel(2), stageLabel(9), stageLabel(10)]).toEqual(['Grid & skala', 'Dokumen', 'Publikasi'])
  })
})

describe('incomplete event logs (restart, shutdown)', () => {
  it('run.finished closes stages that never got stage.finished', () => {
    let run: Run = emptyRun('r1', 'regenerate')
    run = applyEvent(run, ev('stage.started', 7))
    run = applyEvent(run, ev('run.finished', null, { status: 'failed', error: 'interrupted' }))
    expect([run.status, run.stages[7].status]).toEqual(['failed', 'failed'])
  })

  it('a finished run snapshot is not reopened by replaying its events', () => {
    const done: Run = { ...emptyRun('r1', 'regenerate'), status: 'succeeded' }
    const run = withEvents(done, [ev('run.started', null), ev('stage.started', 8)])
    expect([run.status, run.stages[8].status]).toEqual(['succeeded', 'pending'])
  })

  it('an active run snapshot still follows live events', () => {
    const run = withEvents({ ...emptyRun('r1', 'regenerate'), status: 'running' }, [ev('stage.started', 8)])
    expect(run.stages[8].status).toBe('running')
  })
})
