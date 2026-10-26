import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, ApiError } from '../api/client'
import type { Spec } from '../types/spec'
import { rebasePreview } from './ops/compose'
import type { OpFailure } from './ops/reducer'
import { useEditorStore, type Issue } from './store'

export const AUTO_REGENERATE_KEY = 'editor.autoRegenerate'

export function autoRegenerate(): boolean {
  try {
    return localStorage.getItem(AUTO_REGENERATE_KEY) === '1'
  } catch {
    return false
  }
}

/** POST /specs with the local ops: 201 moves the base, 409 offers a rebase, 422 lists issues, 400 names the op. */
export function useSave(projectId: string, regenerate: (version: number) => void) {
  const qc = useQueryClient()
  const [saving, setSaving] = useState(false)
  const [conflict, setConflict] = useState<{ head: Spec; failed: OpFailure[] } | null>(null)

  const save = async (message?: string) => {
    const s = useEditorStore.getState()
    if (!s.ops.length || s.baseVersion === null || saving) return
    setSaving(true)
    try {
      const r = await api.post<{ version: number; spec: Spec; issues: Issue[] }>(`/api/projects/${projectId}/specs`,
        { base_version: s.baseVersion, ops: s.ops, message: message ?? `Edit editor: ${s.ops.length} op` })
      s.markSaved(r.spec)
      for (const k of ['spec', 'specs', 'project']) qc.invalidateQueries({ queryKey: [k, projectId] })
      if (autoRegenerate()) {
        s.setNotice({ kind: 'info', text: `Tersimpan sebagai v${r.version}; regenerate dimulai` })
        regenerate(r.version)
      } else {
        s.setNotice({ kind: 'info', text: `Tersimpan sebagai v${r.version}`, action: { label: 'Regenerate', onClick: () => regenerate(r.version) } })
      }
    } catch (e) {
      if (!(e instanceof ApiError)) return s.setNotice({ kind: 'error', text: String(e) })
      if (e.status === 409 && e.code === 'spec_conflict') {
        const head = await api.get<Spec>(`/api/projects/${projectId}/specs/HEAD`)
        setConflict({ head, failed: rebasePreview(head, useEditorStore.getState().ops) })
      } else if (e.status === 422) {
        s.setSaveIssues((e.details.issues as Issue[]) ?? [])
        s.setNotice({ kind: 'error', text: 'Validasi gagal: perbaiki masalah di panel Masalah, lalu Save lagi' })
      } else if (e.code === 'bad_op') {
        s.setNotice({ kind: 'error', text: `Op #${Number(e.details.index ?? 0) + 1} (${e.details.op}) ditolak: ${e.message}` })
      } else {
        s.setNotice({ kind: e.status === 409 ? 'warning' : 'error', text: e.message })
      }
    } finally {
      setSaving(false)
    }
  }

  const resolve = (accept: boolean) => {
    if (accept && conflict) useEditorStore.getState().acceptRebase(conflict.head, conflict.failed.map((f) => f.index))
    setConflict(null)
  }

  return { save, saving, conflict, resolve }
}
