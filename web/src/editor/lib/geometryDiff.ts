import type { Opening, Spec, Stair, Wall } from '../../types/spec'

export interface Diff<T> { id: string; state: 'added' | 'moved' | 'deleted'; el: T }

const KEYS = { walls: ['a', 'b', 'thickness', 'kind'], openings: ['wall_id', 'offset', 'width'], stairs: ['flights'] } as const

function diff<T extends { id: string }>(base: T[] = [], view: T[] = [], keys: readonly string[]): Diff<T>[] {
  const before = new Map(base.map((e) => [e.id, e]))
  const now = new Set(view.map((e) => e.id))
  const sig = (e: T) => JSON.stringify(keys.map((k) => (e as Record<string, unknown>)[k]))
  const out: Diff<T>[] = []
  for (const el of view) {
    const old = before.get(el.id)
    if (!old) out.push({ id: el.id, state: 'added', el })
    else if (sig(old) !== sig(el)) out.push({ id: el.id, state: 'moved', el })
  }
  for (const el of base) if (!now.has(el.id)) out.push({ id: el.id, state: 'deleted', el })
  return out
}

/** Geometry the shell does not show yet (it changes only after Save + Regenerate). */
export function geometryDiff(base: Spec, view: Spec): { walls: Diff<Wall>[]; openings: Diff<Opening>[]; stairs: Diff<Stair>[] } {
  return {
    walls: diff(base.walls, view.walls, KEYS.walls),
    openings: diff(base.openings, view.openings, KEYS.openings),
    stairs: diff(base.stairs, view.stairs, KEYS.stairs),
  }
}

export const isEmptyDiff = (d: ReturnType<typeof geometryDiff>) => !d.walls.length && !d.openings.length && !d.stairs.length
