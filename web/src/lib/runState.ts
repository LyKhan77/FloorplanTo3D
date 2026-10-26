import type { ApiEvent, Run, RunKind, Stage, StageStatus } from '../api/types'

export const STAGE_NAMES = ['input', 'preprocess', 'grid', 'extract', 'rooms', 'validate', 'review', 'build', 'verify',
  'report', 'publish']
const LABELS = ['Input', 'Preprocess', 'Grid & skala', 'Ekstraksi', 'Ruang', 'Validasi', 'Review Strata', 'Build',
  'Verifikasi', 'Dokumen', 'Publikasi']

export function stageLabel(n: number): string {
  return LABELS[n] ?? `Tahap ${n}`
}

export function emptyRun(runId: string, kind: RunKind): Run {
  const stages: Stage[] = STAGE_NAMES.map((name, n) => ({
    n, name, status: 'pending', started_at: null, ended_at: null, duration_ms: null, progress: null, metrics: {},
    warnings: [],
  }))
  return {
    run_id: runId, project_id: '', kind, from_stage: 0, version: null, spec_version_in: null, spec_version_out: null,
    status: 'queued', stages, code_version: '', blender_version: null, created_at: '', error: null,
  }
}

/** Pure reducer: live SSE events update a run without refetching it. */
export function applyEvent(run: Run, e: ApiEvent): Run {
  if (e.run_id !== run.run_id) return run
  const stages = run.stages.slice()
  const n = e.stage
  const patchStage = (patch: Partial<Stage>) => {
    if (n === null || !stages[n]) return
    stages[n] = { ...stages[n], ...patch }
  }
  switch (e.type) {
    case 'run.started':
      return { ...run, status: 'running' }
    case 'run.finished':  // a stage left running (restart, shutdown) never gets its stage.finished
      return { ...run, status: (e.data.status as Run['status']) ?? run.status, error: (e.data.error as string) ?? null,
        stages: stages.map((s) => (s.status === 'running' ? { ...s, status: 'failed' } : s)) }
    case 'stage.started':
      patchStage({ status: 'running', started_at: e.ts })
      return { ...run, status: 'running', stages }
    case 'stage.progress':
      patchStage({ progress: Number(e.data.percent ?? 0) })
      return { ...run, stages }
    case 'stage.finished':
      patchStage({ status: e.data.status as StageStatus, duration_ms: Number(e.data.duration_ms ?? 0), ended_at: e.ts })
      return { ...run, stages }
    default:
      return run
  }
}

/** The stored run plus live events. A finished snapshot is final: the event log can miss events (shutdown), so
 * replaying it could reopen the run. */
export function withEvents(run: Run, events: ApiEvent[]): Run {
  if (run.status !== 'queued' && run.status !== 'running') return run
  return events.reduce(applyEvent, run)
}
