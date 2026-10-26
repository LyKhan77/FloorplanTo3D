import type { ApiEvent } from '../api/types'
import { formatDuration } from './format'

export interface LogLine {
  time: string
  stage: string
  level: string
  msg: string
}

export interface LogFilter {
  runId: string | null
  stages: number[]
  levels: string[]
  q: string
}

/** `HH:MM:SS.mmm  [S3]  INFO  message` (PRD/08 §3.3). The clock comes from the server timestamp as written. */
export function formatLogLine(e: ApiEvent): LogLine {
  const time = e.ts.split('T')[1]?.slice(0, 12) ?? e.ts
  let msg = e.msg
  if (!msg) {
    const parts = [e.type]
    if (typeof e.data.status === 'string') parts.push(e.data.status)
    if (typeof e.data.duration_ms === 'number') parts.push(formatDuration(e.data.duration_ms))
    if (typeof e.data.percent === 'number') parts.push(`${e.data.percent}% ${e.data.msg ?? ''}`.trim())
    if (typeof e.data.version === 'number') parts.push(`v${e.data.version}`)
    msg = parts.join(' · ')
  }
  return { time, stage: e.stage === null ? '[--]' : `[S${e.stage}]`, level: e.level.toUpperCase(), msg }
}

export function filterEvents(events: ApiEvent[], f: LogFilter): ApiEvent[] {
  const q = f.q.trim().toLowerCase()
  return events.filter((e) =>
    (!f.runId || e.run_id === f.runId)
    && (!f.stages.length || (e.stage !== null && f.stages.includes(e.stage)))
    && (!f.levels.length || f.levels.includes(e.level))
    && (!q || formatLogLine(e).msg.toLowerCase().includes(q)))
}
