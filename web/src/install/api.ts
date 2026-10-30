import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { Installation } from '../types/installation'
import type { InstallOp } from './reducer'

type Pt = [number, number]
const P = (pid: string) => `/api/projects/${pid}/installations`

export interface InstallIssue { code: string; severity: 'error' | 'warning' | 'info'; element_ids: string[]; message: string }
export interface Drop { rack_id: string; tray_id: string; tray_class: 'data' | 'power'; at: Pt; to: Pt; horizontal: number; vertical: number }
export type Lengths = Record<'data' | 'power', { horizontal: number; drops: number; total: number }>
export interface InstallValidation { issues: InstallIssue[]; drops: Drop[]; lengths: Lengths | null; pending: boolean; error: string | null }
export interface SnapBox { center: Pt; size: Pt; rotation: number; template_id: string | null; template_version?: string; dims?: [number, number, number] }

export const useInstallation = (pid: string, enabled = true) => useQuery({
  queryKey: ['installation', pid], enabled,
  queryFn: () => api.get<Installation>(`${P(pid)}/HEAD`).catch((e) => { if (e instanceof ApiError && e.status === 404) return null; throw e }),
})

export const startInstallation = (pid: string, body: { ceiling_height: number | null; raised_floor_height: number | null; default_mounting: 'overhead' | 'underfloor' }) =>
  api.post<Installation>(`${P(pid)}/start`, body)
export const saveInstallation = (pid: string, base: number, ops: InstallOp[], message = '') =>
  api.post<{ version: number; installation: Installation; issues: InstallIssue[]; lengths: Lengths }>(P(pid), { base_version: base, ops, message })
export const rebaseInstallation = (pid: string) => api.post<{ version: number; issues: InstallIssue[] }>(`${P(pid)}/rebase`)
export const snapTray = (pid: string, points: Pt[]) => api.post<{ path: Pt[]; width: number }>(`${P(pid)}/snap-tray`, { points })
export const snapBox = (pid: string, at: Pt) => api.post<SnapBox>(`${P(pid)}/snap-box`, { at })
export const snapBoxes = (pid: string, a: Pt, b: Pt) => api.post<SnapBox[]>(`${P(pid)}/snap-boxes`, { a, b })

/** Live dry run of the pending ops (POST /installations/validate), debounced 300 ms; the base answer while none are pending. */
export function useInstallValidate(pid: string, base: number | null, ops: InstallOp[]): InstallValidation {
  const [done, setDone] = useState<{ key: string; issues: InstallIssue[]; drops: Drop[]; lengths: Lengths | null; error: string | null } | null>(null)
  const key = `${base}|${JSON.stringify(ops)}`
  useEffect(() => {
    if (base === null) return
    let live = true
    const t = setTimeout(() => {
      api.post<{ issues: InstallIssue[]; drops: Drop[]; lengths: Lengths }>(`${P(pid)}/validate`, { base_version: base, ops })
        .then((r) => { if (live) setDone({ key, ...r, error: null }) })
        .catch((e: unknown) => { if (live) setDone((prev) => ({ key, issues: [], drops: prev?.drops ?? [], lengths: prev?.lengths ?? null, error: e instanceof Error ? e.message : String(e) })) })
    }, ops.length ? 300 : 0)
    return () => { live = false; clearTimeout(t) }
  }, [pid, base, ops, key])
  return useMemo(() => ({ issues: done?.issues ?? [], drops: done?.drops ?? [], lengths: done?.lengths ?? null,
    pending: done?.key !== key, error: done?.key === key ? done.error : null }), [done, key])
}
