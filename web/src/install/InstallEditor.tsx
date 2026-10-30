import { Redo, Save, Undo } from '@carbon/icons-react'
import { Button, InlineNotification } from '@carbon/react'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { ApiError } from '../api/client'
import type { Backdrop } from '../api/types'
import { saveInstallation, useInstallation, useInstallValidate, type InstallIssue } from './api'
import { InstallPanels } from './InstallPanels'
import { InstallWorkspace } from './InstallWorkspace'
import { useInstallStore } from './store'

/** Mode Instalasi of the editor tab (M12a): trace, check, save. The layout stays read-only here. */
export function InstallEditor({ projectId, backdrop }: { projectId: string; backdrop: Backdrop | null }) {
  const qc = useQueryClient()
  const { data: head } = useInstallation(projectId)
  const base = useInstallStore((s) => s.base)
  const ops = useInstallStore((s) => s.ops)
  const past = useInstallStore((s) => s.past)
  const future = useInstallStore((s) => s.future)
  const notice = useInstallStore((s) => s.notice)
  const validation = useInstallValidate(projectId, base?.meta.version ?? null, ops)
  const [saving, setSaving] = useState(false)
  const [saveIssues, setSaveIssues] = useState<InstallIssue[]>([])

  // a newer HEAD (another tab, a rebase) replaces the base only while nothing is pending here
  useEffect(() => {
    const s = useInstallStore.getState()
    if (head && (!s.base || (!s.ops.length && s.base.meta.version !== head.meta.version))) s.load(head)
  }, [head])

  const save = async () => {
    const s = useInstallStore.getState()
    if (!s.base || !s.ops.length) return
    setSaving(true)
    try {
      const r = await saveInstallation(projectId, s.base.meta.version ?? 0, s.ops)
      s.load(r.installation)
      setSaveIssues([])
      s.setNotice({ kind: 'info', text: `Instalasi tersimpan sebagai v${r.version}` })
      for (const k of ['installation', 'project']) qc.invalidateQueries({ queryKey: [k, projectId] })
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setSaveIssues((e.details.issues as InstallIssue[]) ?? [])
        s.setNotice({ kind: 'error', text: 'Validasi gagal: perbaiki masalah di panel Masalah, lalu Save lagi' })
      } else {
        s.setNotice({ kind: 'error', text: e instanceof Error ? e.message : String(e) })
      }
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return
      const k = e.key.toLowerCase()
      if (k === 'z') { e.preventDefault(); if (e.shiftKey) useInstallStore.getState().redo(); else useInstallStore.getState().undo() }
      if (k === 's') { e.preventDefault(); void save() }
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  })

  return (
    <div className="editor install-editor">
      <div className="editor__toolbar" role="toolbar" aria-label="Toolbar instalasi">
        <span className="editor__group">
          <Button kind="ghost" size="sm" hasIconOnly renderIcon={Undo} iconDescription="Undo (Ctrl+Z)" tooltipPosition="bottom" disabled={!past.length}
            onClick={() => useInstallStore.getState().undo()} />
          <Button kind="ghost" size="sm" hasIconOnly renderIcon={Redo} iconDescription="Redo (Ctrl+Shift+Z)" tooltipPosition="bottom" disabled={!future.length}
            onClick={() => useInstallStore.getState().redo()} />
        </span>
        <span className="editor__version mono">{base ? `instalasi v${base.meta.version} · layout v${base.meta.layout_version}` : '—'}{ops.length ? ` (unsaved: ${ops.length})` : ''}</span>
        <span className="editor__spacer" />
        <Button size="sm" kind="primary" renderIcon={Save} disabled={!ops.length || saving} onClick={() => void save()}>{saving ? 'Menyimpan…' : 'Save'}</Button>
      </div>
      <aside className="editor__library" aria-label="Info instalasi">
        <p className="helper">Telusuri tray dan rack dari denah. Build 3D instalasi menyusul (M12b).</p>
      </aside>
      <div className="editor__viewport">
        {notice && <InlineNotification kind={notice.kind} lowContrast title="" subtitle={notice.text} onClose={() => useInstallStore.getState().setNotice(null)} />}
        <div className="editor__canvas editor__canvas--plan">
          <InstallWorkspace projectId={projectId} backdrop={backdrop} drops={validation.drops} />
        </div>
      </div>
      <aside className="editor__props" aria-label="Properti">
        <InstallPanels validation={validation} saveIssues={saveIssues} />
      </aside>
    </div>
  )
}
