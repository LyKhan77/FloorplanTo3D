import { api, ApiError } from '../../api/client'
import type { EditorOp } from '../ops/reducer'

type Pt = [number, number]
export interface Proposal {
  ops: EditorOp[]
  deleted: string[]
  added: { a: Pt; b: Pt; thickness: number; snapped: boolean }[]
  moved: { id: string; a: Pt; b: Pt }[]
  openings: { a: Pt; b: Pt; category: 'door' | 'window'; snapped: boolean }[]
  stairs: { flights: { start: Pt; end: Pt; width: number; risers: number }[]; landings: Pt[][]; snapped: boolean }[]
  objects: { template_id: string; corners: Pt[]; front: [Pt, Pt]; zones: Pt[][]; z: number; snapped: boolean }[]
  explanation: string
  notes: string[]
  issues: { code: string; severity: string; message: string }[]
  valid: boolean
}
export type AssistEvent =
  | { event: 'session'; session_id: string }
  | { event: 'step' | 'question' | 'error'; text: string }
  | ({ event: 'proposal' } & Proposal)
  | { event: 'done' }
export interface AssistBody {
  session_id?: string
  base_version: number
  ops: EditorOp[]
  box: [number, number, number, number]
  selection: string[]
  message: string
  drawn?: DrawnBox[]
  layer?: 'layout' | 'installation'
}
/** A box the user pointed at in the drawing (generate interior): centre, [short, long] mm, long side along y (0) or x (90). */
export interface DrawnBox { id: string; center: Pt; size: [number, number]; rotation: 0 | 90 }

/** POST /assist/area and hand each Server-Sent Event to `onEvent` as it arrives. */
export async function streamAssist(pid: string, body: AssistBody, onEvent: (e: AssistEvent) => void): Promise<void> {
  const res = await fetch(`/api/projects/${pid}/assist/area`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!res.ok || !res.body) {
    const e = (await res.json().catch(() => ({})))?.error ?? {}
    throw new ApiError(res.status, e.code ?? 'http_error', e.message ?? res.statusText, e.details ?? {})
  }
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    buf += dec.decode(value, { stream: !done })
    let cut
    while ((cut = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, cut)
      buf = buf.slice(cut + 2)
      const lines = Object.fromEntries(block.split('\n').map((l) => [l.slice(0, l.indexOf(':')), l.slice(l.indexOf(':') + 1).trim()]))
      if (lines.event) onEvent({ event: lines.event, ...JSON.parse(lines.data || '{}') } as AssistEvent)
    }
    if (done) return
  }
}

export const drawnBox = (pid: string, at: { at: Pt } | { a: Pt; b: Pt }) =>
  api.post<Omit<DrawnBox, 'id'>>(`/api/projects/${pid}/assist/drawn-box`, at)

export const postDecision = (pid: string, sid: string, accepted: boolean) =>
  api.post<void>(`/api/projects/${pid}/assist/area/${sid}/decision`, { accepted })
