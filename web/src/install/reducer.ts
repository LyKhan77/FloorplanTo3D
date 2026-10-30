import type { CableTray, Installation, PlacedObject } from '../types/installation'

/** Client mirror of core/installation/ops.py for the instant preview; the server stays the authority on Save. */
type Pt = [number, number]
type TrayFields = { tray_class?: 'data' | 'power'; width?: number; side_height?: number; mounting?: 'overhead' | 'underfloor' | null
  elevation?: number | null; flow?: 'forward' | 'reverse' }
export type InstallOp =
  | ({ op: 'add_tray'; path: Pt[]; tray_class: 'data' | 'power' } & TrayFields)
  | ({ op: 'set_tray'; id: string } & TrayFields)
  | { op: 'move_tray_path'; id: string; path: Pt[]; reason: string }
  | { op: 'delete_tray'; id: string; reason: string }
  | { op: 'set_installation_meta'; ceiling_height?: number | null; raised_floor_height?: number | null; default_mounting?: 'overhead' | 'underfloor' }
  | { op: 'add_object'; template_id: string; template_version: string; position: [number, number, number]; rotation?: number
      dims: [number, number, number]; label?: string | null; evidence?: Record<string, unknown> }
  | { op: 'update_object'; id: string; position?: [number, number, number]; rotation?: number; label?: string | null; reason?: string
      template_id?: string; template_version?: string; dims?: [number, number, number] }
  | { op: 'delete_object'; id: string; reason: string }
export interface InstallOpFailure { index: number; op: string; message: string }

export const TRAY_WIDTHS = [100, 150, 200, 300, 400, 500, 600]
export const SIDE_HEIGHTS = [50, 100, 150]
export const DEFAULT_WIDTH = { data: 200, power: 400 } as const
const MIN_STEP_MM = 100

/** Points closer than 100 mm to the previous one are double clicks, not corners. */
export function cleanPath(points: Pt[]): Pt[] {
  return points.reduce<Pt[]>((out, p) => (out.length && Math.hypot(p[0] - out.at(-1)![0], p[1] - out.at(-1)![1]) < MIN_STEP_MM ? out : [...out, p]), [])
}

function take(s: Installation, prefix: string): string {
  const seq = (s.meta.id_seq ??= {}) as Record<string, number>
  const used = [...(s.cable_trays ?? []), ...(s.objects ?? [])].map((x) => x.id.match(new RegExp(`^${prefix}(\\d+)$`))).filter(Boolean).map((m) => Number(m![1]))
  const n = Math.max(seq[prefix] ?? 0, ...used, 0) + 1
  seq[prefix] = n
  return `${prefix}${n}`
}

function find<T extends { id: string }>(items: T[] | undefined, id: string): T {
  const it = items?.find((x) => x.id === id)
  if (!it) throw new Error(`unknown id ${id}`)
  return it
}

const given = (op: object, skip: string[]) => Object.fromEntries(Object.entries(op).filter(([k, v]) => !skip.includes(k) && v !== undefined))

function step(s: Installation, op: InstallOp): void {
  switch (op.op) {
    case 'add_tray': {
      const id = take(s, 'T')
      ;(s.cable_trays ??= []).push({ side_height: 100, tray_type: 'perforated', mounting: null, elevation: null, flow: 'forward',
        ...given(op, ['op']), id, width: op.width ?? DEFAULT_WIDTH[op.tray_class] } as CableTray)
      return
    }
    case 'set_tray':
    case 'move_tray_path':
      Object.assign(find(s.cable_trays, op.id), given(op, ['op', 'id', 'reason']))
      return
    case 'delete_tray':
      find(s.cable_trays, op.id)
      s.cable_trays = s.cable_trays!.filter((t) => t.id !== op.id)
      return
    case 'set_installation_meta':
      Object.assign(s.meta, given(op, ['op']))
      return
    case 'add_object':
      ;(s.objects ??= []).push({ rotation: 0, locked: false, ...given(op, ['op', 'evidence']), id: take(s, 'O') } as PlacedObject)
      return
    case 'update_object':
      Object.assign(find(s.objects, op.id), given(op, ['op', 'id', 'reason']))
      return
    case 'delete_object':
      find(s.objects, op.id)
      s.objects = s.objects!.filter((o) => o.id !== op.id)
  }
}

/** Pure: never mutates `base`. A failing op is skipped (the server is atomic), later ops still apply. */
export function applyInstallOps(base: Installation, ops: InstallOp[]): { inst: Installation; failed: InstallOpFailure[] } {
  const inst = structuredClone(base)
  const failed: InstallOpFailure[] = []
  ops.forEach((op, index) => {
    try { step(inst, op) } catch (e) { failed.push({ index, op: op.op, message: (e as Error).message }) }
  })
  return { inst, failed }
}
