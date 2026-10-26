import { useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { EditorOp } from './ops/reducer'
import type { Issue } from './store'

interface Result { issues: Issue[] }
const key = (i: Issue) => `${i.code}|${i.element_ids.join(',')}`

/** Live dry-run of the local ops (POST /specs/validate), debounced 500 ms; issues absent from the base are "new". */
export function useValidate(projectId: string, baseVersion: number | null, ops: EditorOp[]) {
  const [base, setBase] = useState<{ version: number | null; issues: Issue[] }>({ version: null, issues: [] })
  const [done, setDone] = useState<{ ops: EditorOp[] | null; issues: Issue[]; error: string | null }>({ ops: null, issues: [], error: null })
  const url = `/api/projects/${projectId}/specs/validate`

  useEffect(() => {
    if (baseVersion === null) return
    let live = true
    api.post<Result>(url, { base_version: baseVersion, ops: [] })
      .then((r) => { if (live) setBase({ version: baseVersion, issues: r.issues }) })
      .catch(() => { if (live) setBase({ version: baseVersion, issues: [] }) })
    return () => { live = false }
  }, [url, baseVersion])

  useEffect(() => {
    if (baseVersion === null || !ops.length) return
    let live = true
    const t = setTimeout(() => {
      api.post<Result>(url, { base_version: baseVersion, ops })
        .then((r) => { if (live) setDone({ ops, issues: r.issues, error: null }) })
        .catch((e: unknown) => {
          if (!live) return
          const msg = e instanceof ApiError && e.code === 'bad_op'
            ? `Op #${Number(e.details.index ?? 0) + 1}: ${e.message}` : e instanceof Error ? e.message : String(e)
          setDone({ ops, issues: [], error: msg })
        })
    }, 500)
    return () => { live = false; clearTimeout(t) }
  }, [url, baseVersion, ops])

  return useMemo(() => {
    if (!ops.length) return { issues: base.issues, newIssues: new Set<string>(), error: null, pending: false }
    const known = new Set(base.issues.map(key))
    return {
      issues: done.issues,
      newIssues: new Set(done.issues.map(key).filter((k) => !known.has(k))),
      error: done.ops === ops ? done.error : null,
      pending: done.ops !== ops,
    }
  }, [ops, base, done])
}
