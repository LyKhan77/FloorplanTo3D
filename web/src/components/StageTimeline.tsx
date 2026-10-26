import type { Run } from '../api/types'
import { formatDuration } from '../lib/format'
import { stageLabel } from '../lib/runState'
import { StatusTag } from './StatusTag'

/** Vertical stage list (PRD/08 §3.3). A plain list of buttons so every status keeps its own icon and text. */
export function StageTimeline({ run, selected, onSelect }: { run: Run; selected: number; onSelect: (n: number) => void }) {
  return (
    <ol className="stage-timeline" aria-label="Tahap pipeline">
      {run.stages.map((s) => (
        <li key={s.n}>
          <button type="button" className={`stage-step${s.n === selected ? ' stage-step--selected' : ''}`}
            aria-current={s.n === selected ? 'step' : undefined} onClick={() => onSelect(s.n)}>
            <span className="stage-step__name"><span className="mono">{s.n}</span> {stageLabel(s.n)}</span>
            <span className="stage-step__meta">
              <StatusTag status={s.status} warning={s.status === 'succeeded' && s.warnings.length > 0} />
              <span className="mono stage-step__time">
                {s.status === 'running' && s.progress !== null ? `${s.progress}%` : formatDuration(s.duration_ms)}
              </span>
            </span>
          </button>
        </li>
      ))}
    </ol>
  )
}
