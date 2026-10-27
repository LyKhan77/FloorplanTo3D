import type { Stage, TranscriptLine } from '../api/types'

const REASONS: Record<string, string> = {
  disabled: 'tidak ada tugas Strata yang aktif',
  disabled_by_user: 'Strata dimatikan untuk run ini',
  no_artifacts: 'artefak tahap 1–5 run ini tidak ada',
  strata_unavailable: 'Strata tidak tersedia',
}

/** One line for the stage-6 panel: the skip reason, or the review counts and score change. */
export function strataSummary(stage: Stage, lastMessage?: string): string {
  const m = stage.metrics as Record<string, number | string | undefined>
  if (stage.status === 'skipped') return `Review Strata dilewati: ${REASONS[String(m.reason)] ?? 'tahap dilewati'}`
  if (typeof m.reviewed === 'number') {
    const score = (v: unknown) => (typeof v === 'number' ? v.toFixed(3) : '—')
    return `Diperiksa ${m.reviewed} · diterima ${m.accepted ?? 0} · ditolak ${m.rejected ?? 0} · skor ${score(m.score_before)} → ${score(m.score_after)}`
  }
  return lastMessage ?? '—'
}

/** Strata's answer without its id: "annotation", "pintu · single_swing · end", "delete_wall W3". */
export function verdictText(v: Record<string, unknown> | null): string {
  if (!v) return '—'
  if (typeof v.tool === 'string') {
    const args = (v.arguments ?? {}) as { id?: string; ids?: string[] }
    return [v.tool, args.ids?.join(',') ?? args.id].filter(Boolean).join(' ')
  }
  return Object.entries(v).filter(([k, x]) => k !== 'id' && x !== null && x !== undefined)
    .map(([k, x]) => (k === 'is_door' ? (x ? 'pintu' : 'bukan pintu') : String(x))).join(' · ')
}

/** transcript.jsonl lines; a torn or broken line is skipped. */
export function parseTranscript(text: string): TranscriptLine[] {
  return text.split('\n').flatMap((line) => {
    if (!line.trim()) return []
    try { return [JSON.parse(line) as TranscriptLine] } catch { return [] }
  })
}
