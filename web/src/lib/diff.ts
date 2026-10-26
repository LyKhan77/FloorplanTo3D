import type { SpecDiff } from '../api/types'

const LABELS: Record<string, string> = {
  walls: 'Dinding', columns: 'Kolom', openings: 'Bukaan', rooms: 'Ruang', stairs: 'Tangga', objects: 'Objek',
}

export function summarizeDiff(d: SpecDiff): string[] {
  return Object.keys(LABELS)
    .filter((t) => d[t] && (d[t].added.length || d[t].removed.length || d[t].changed.length))
    .map((t) => `${LABELS[t]}: +${d[t].added.length} −${d[t].removed.length} ~${d[t].changed.length}`)
}
