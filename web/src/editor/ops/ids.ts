import type { Spec } from '../../types/spec'

/** Mirror of core/spec/ids.py: IDs are never reused, even after the top one is deleted. */
const ID_RE = /^([A-Z]+)(\d+)$/

export function idKey(id: string): [string, number] {
  const m = ID_RE.exec(id)
  return m ? [m[1], Number(m[2])] : [id, 0]
}

export function compareIds(a: string, b: string): number {
  const [pa, na] = idKey(a), [pb, nb] = idKey(b)
  return pa < pb ? -1 : pa > pb ? 1 : na - nb
}

export function allIds(spec: Spec): string[] {
  const groups = [spec.grid?.axes, spec.walls, spec.columns, spec.openings, spec.rooms, spec.stairs, spec.objects]
  return groups.flatMap((g) => (g ?? []).map((e) => e.id))
}

export function seedIdSeq(spec: Spec): void {
  const seq = (spec.meta.id_seq ??= {})
  for (const id of allIds(spec)) {
    const m = ID_RE.exec(id)
    if (m) seq[m[1]] = Math.max(seq[m[1]] ?? 0, Number(m[2]))
  }
}

export function takeId(spec: Spec, prefix: string): string {
  const seq = (spec.meta.id_seq ??= {})
  const used = allIds(spec).map((id) => ID_RE.exec(id)).filter((m) => m && m[1] === prefix).map((m) => Number(m![2]))
  const n = Math.max(seq[prefix] ?? 0, ...used) + 1
  seq[prefix] = n
  return `${prefix}${n}`
}
