import { useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { ReviewTask } from '../api/types'
import type { Room } from '../types/spec'
import type { EditorOp } from './ops/reducer'
import type { Issue } from './store'

interface Result { issues: Issue[]; rooms?: Room[]; tasks?: ReviewTask[] }
type Review = { rooms: Room[] | null; tasks: ReviewTask[] | null }
const key = (i: Issue) => `${i.code}|${i.element_ids.join(',')}`

/** Live dry-run of the local ops (POST /specs/validate), debounced 500 ms; issues absent from the base are "new". */
export function useValidate(projectId: string, baseVersion: number | null, ops: EditorOp[]) {
  const [base, setBase] = useState<{ version: number | null; issues: Issue[] } & Review>({ version: null, issues: [], rooms: null, tasks: [] })
  const [done, setDone] = useState<{ ops: EditorOp[] | null; issues: Issue[]; error: string | null } & Review>(
    { ops: null, issues: [], error: null, rooms: null, tasks: [] })
  const url = `/api/projects/${projectId}/specs/validate`

  useEffect(() => {
    if (baseVersion === null) return
    let live = true
    api.post<Result>(url, { base_version: baseVersion, ops: [] })
      .then((r) => { if (live) setBase({ version: baseVersion, issues: r.issues, rooms: r.rooms ?? null, tasks: r.tasks ?? [] }) })
      .catch(() => { if (live) setBase({ version: baseVersion, issues: [], rooms: null, tasks: [] }) })
    return () => { live = false }
  }, [url, baseVersion])

  useEffect(() => {
    if (baseVersion === null || !ops.length) return
    let live = true
    const t = setTimeout(() => {
      api.post<Result>(url, { base_version: baseVersion, ops })
        .then((r) => { if (live) setDone({ ops, issues: r.issues, error: null, rooms: r.rooms ?? null, tasks: r.tasks ?? [] }) })
        .catch((e: unknown) => {
          if (!live) return
          const msg = e instanceof ApiError && e.code === 'bad_op'
            ? `Op #${Number(e.details.index ?? 0) + 1}: ${e.message}` : e instanceof Error ? e.message : String(e)
          // keep the last rooms and tasks: an error must not look like every review task got done
          setDone((prev) => ({ ops, issues: [], error: msg, rooms: prev.rooms, tasks: prev.ops ? prev.tasks : null }))
        })
    }, 500)
    return () => { live = false; clearTimeout(t) }
  }, [url, baseVersion, ops])

  return useMemo(() => {
    if (!ops.length) return { issues: base.issues, newIssues: new Set<string>(), error: null, pending: false, rooms: base.rooms, tasks: base.tasks ?? [] }
    const known = new Set(base.issues.map(key))
    return {
      issues: done.issues,
      newIssues: new Set(done.issues.map(key).filter((k) => !known.has(k))),
      error: done.ops === ops ? done.error : null,
      pending: done.ops !== ops,
      // M8: rooms rebuilt by the server for these ops, and the review tasks left; the last answer while one is pending
      rooms: done.rooms ?? base.rooms,
      tasks: (done.ops ? done.tasks : null) ?? base.tasks ?? [],
    }
  }, [ops, base, done])
}
