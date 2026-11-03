import { Maximize, Minimize, Redo, Renew, Save, Undo } from '@carbon/icons-react'
import { Button, InlineNotification, ProgressBar } from '@carbon/react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { Backdrop, Run } from '../api/types'
import { ignoredTarget } from '../editor/lib/keys'
import { useProject, useRuns } from '../api/hooks'
import { stageLabel } from '../lib/runState'
import type { Installation } from '../types/installation'
import { buildInstallation, ensureInstallation, outputUrl, saveInstallation, useInstallation, useInstallOutputs, useInstallValidate, type InstallIssue } from './api'
import { RebaseNotice } from './InstallationBanner'
import { InstallViewer } from './InstallViewer'
import { LibraryPanel } from '../editor/panels/LibraryPanel'
import { AssistPanel } from '../editor/assist/AssistPanel'
import type { Template } from '../api/types'
import { InstallPanels } from './InstallPanels'
import { InstallWorkspace } from './InstallWorkspace'
import { useInstallStore } from './store'

/** Mode Instalasi of the editor tab (M12a): trace, check, save. The layout stays read-only here. */
export function InstallEditor({ projectId, backdrop, templates }: { projectId: string; backdrop: Backdrop | null;
  templates?: Template[] }) {
  const qc = useQueryClient()
  const { data: head } = useInstallation(projectId)
  const base = useInstallStore((s) => s.base)
  const ops = useInstallStore((s) => s.ops)
  const past = useInstallStore((s) => s.past)
  const future = useInstallStore((s) => s.future)
  const notice = useInstallStore((s) => s.notice)
  const tool = useInstallStore((s) => s.tool)
  // opening Instalasi & Interior: the installation exists, holds every device and stands on the newest layout
  // (never over unsaved work: then the Rebase notice asks to Save first)
  useEffect(() => {
    const s = useInstallStore.getState()
    if (s.projectId === projectId && s.ops.length) return
    ensureInstallation(projectId).then((r) => {
      const st = useInstallStore.getState()
      if (st.projectId === projectId && st.ops.length) return
      st.load(r.installation, projectId)
      qc.setQueryData(['installation', projectId], r.installation)
      for (const k of ['project', 'spec']) qc.invalidateQueries({ queryKey: [k, projectId] })
      if (r.notes.length) st.setNotice({ kind: r.issues.length ? 'warning' : 'info', text: r.notes.join('; ') })
    }).catch((e) => useInstallStore.getState().setNotice({ kind: 'error', text: e instanceof Error ? e.message : String(e) }))
  }, [projectId, qc])
  const validation = useInstallValidate(projectId, base?.meta.version ?? null, ops)
  const [saving, setSaving] = useState(false)
  const [saveIssues, setSaveIssues] = useState<InstallIssue[]>([])
  const [view3d, setView3d] = useState(false)
  const [full, setFull] = useState(false)
  const [buildRun, setBuildRun] = useState<string | null>(null)
  const { data: outputs = [] } = useInstallOutputs(projectId)
  const { data: project } = useProject(projectId)
  const stale = project?.installation?.layout_changed ? project : null
  const latest = outputs[0]
  // polls the installation run; when it ends: show the outputs (or why it failed) and stop polling
  // a build started before this editor opened (reopened mid-build) is followed too
  const { data: runs = [] } = useRuns(projectId)
  const active = runs.find((r) => r.kind === 'installation' && (r.status === 'queued' || r.status === 'running'))
  const tracked = buildRun ?? active?.run_id ?? null
  const run = useQuery({ queryKey: ['run', projectId, tracked], enabled: !!tracked, refetchInterval: 2000,
    queryFn: async () => {
      const r = await api.get<Run>(`/api/projects/${projectId}/runs/${tracked}`)
      if (['succeeded', 'failed', 'needs_attention'].includes(r.status)) {
        setBuildRun(null)
        for (const k of ['installation-outputs', 'runs']) qc.invalidateQueries({ queryKey: [k, projectId] })
        useInstallStore.getState().setNotice(r.status === 'failed'
          ? { kind: 'error', text: `Build 3D gagal: ${r.error ?? 'lihat tab Pipeline'}` }
          : { kind: 'info', text: 'Build 3D selesai: lihat tampilan 3D dan unduhan di panel kiri' })
        if (r.status !== 'failed') setView3d(true)
      }
      return r
    } })
  const building = !!tracked && !['succeeded', 'failed', 'needs_attention'].includes(run.data?.status ?? '')

  // full screen (F): the installation editor covers the window, the page under it stops scrolling
  useEffect(() => {
    document.body.style.overflow = full ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [full])

  const build = async () => {
    const s = useInstallStore.getState()
    try {  // the server moves the installation onto the newest layout first
      const r = await buildInstallation(projectId)
      setSaveIssues([])
      setBuildRun(r.run_id)
      s.setNotice({ kind: 'info', text: 'Build 3D instalasi berjalan…' })
    } catch (e) {
      if (e instanceof ApiError && e.code === 'installation_invalid') {
        setSaveIssues((e.details.issues as InstallIssue[]) ?? [])
        s.setNotice({ kind: 'error', text: 'Build ditolak: perbaiki error di panel Masalah' })
      } else {
        s.setNotice({ kind: 'error', text: e instanceof Error ? e.message : String(e) })
      }
    }
  }

  // another project's installation is replaced at once; a newer HEAD (another tab, a rebase) only while nothing is pending
  useEffect(() => {
    const s = useInstallStore.getState()
    if (head && (s.projectId !== projectId || !s.base || (!s.ops.length && s.base.meta.version !== head.meta.version))) s.load(head, projectId)
  }, [head, projectId])
  useEffect(() => {
    useInstallStore.getState().setMounted(true)
    return () => useInstallStore.getState().setMounted(false)
  }, [])

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
      if (e instanceof ApiError && e.status === 409) {
        // saved elsewhere first (another tab, a rebase): replay this work on the newer version; ops point at IDs and add_* take fresh ones
        const pending = s.ops
        const newer = await qc.fetchQuery({ queryKey: ['installation', projectId], queryFn: () => api.get<Installation>(`/api/projects/${projectId}/installations/HEAD`) })
        s.load(newer, projectId)
        if (s.applyMany(pending)) s.setNotice({ kind: 'warning', text: `Instalasi berubah di tempat lain (v${newer.meta.version}); perubahan Anda diterapkan ulang. Cek, lalu Save lagi` })
      } else if (e instanceof ApiError && e.status === 422) {
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
      if (e.key.toLowerCase() === 'f' && !e.ctrlKey && !e.metaKey && !e.altKey && !ignoredTarget(e.target as Element | null)) {
        setFull((f) => !f)
        return
      }
      if (!(e.ctrlKey || e.metaKey)) return
      const k = e.key.toLowerCase()
      if (k === 'z') { e.preventDefault(); if (e.shiftKey) useInstallStore.getState().redo(); else useInstallStore.getState().undo() }
      if (k === 's') { e.preventDefault(); void save() }
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  })

  return (
    <div className={`editor install-editor${full ? ' editor--full' : ''}`}>
      <div className="editor__toolbar" role="toolbar" aria-label="Toolbar instalasi">
        <span className="editor__group">
          <Button kind="ghost" size="sm" hasIconOnly renderIcon={Undo} iconDescription="Undo (Ctrl+Z)" tooltipPosition="bottom" disabled={!past.length}
            onClick={() => useInstallStore.getState().undo()} />
          <Button kind="ghost" size="sm" hasIconOnly renderIcon={Redo} iconDescription="Redo (Ctrl+Shift+Z)" tooltipPosition="bottom" disabled={!future.length}
            onClick={() => useInstallStore.getState().redo()} />
        </span>
        <span className="editor__version mono">{base ? `instalasi v${base.meta.version} · layout v${base.meta.layout_version}` : '—'}{ops.length ? ` (unsaved: ${ops.length})` : ''}</span>
        <span className="editor__group" role="group" aria-label="Tampilan">
          <Button size="sm" kind={view3d ? 'ghost' : 'secondary'} aria-pressed={!view3d} onClick={() => setView3d(false)}>2D</Button>
          <Button size="sm" kind={view3d ? 'secondary' : 'ghost'} aria-pressed={view3d} onClick={() => setView3d(true)}>3D</Button>
        </span>
        <span className="editor__spacer" />
        {building && (
          <ProgressBar className="editor__progress" size="small" label={run.data?.stages.find((x) => x.status === 'running') ? stageLabel(run.data.stages.find((x) => x.status === 'running')!.n) : 'antre'}
            helperText="Build 3D instalasi" />
        )}
        <Button size="sm" kind="primary" renderIcon={Save} disabled={!ops.length || saving} onClick={() => void save()}>{saving ? 'Menyimpan…' : 'Save'}</Button>
        <Button size="sm" kind="tertiary" renderIcon={Renew} disabled={!!ops.length || building} title={ops.length ? 'Save dulu' : undefined}
          onClick={() => void build()}>Build 3D</Button>
        <Button kind="ghost" size="sm" hasIconOnly renderIcon={full ? Minimize : Maximize} iconDescription={full ? 'Keluar layar penuh (F)' : 'Layar penuh (F)'}
          tooltipPosition="bottom" aria-pressed={full} onClick={() => setFull(!full)} />
      </div>
      <aside className="editor__library" aria-label="Output instalasi">
        <section className="editor-panel"><LibraryPanel templates={templates ?? []} /></section>
        {stale && <section className="editor-panel"><RebaseNotice project={stale} /></section>}
        <section className="editor-panel">
          <h4 className="editor-panel__title">Output 3D</h4>
          {latest ? (
            <ul className="install-outputs">
              <li className="helper">instalasi v{latest.version}</li>
              {latest.files.filter((f) => !f.startsWith('renders/') && f !== 'report.css').map((f) => (
                <li key={f}>{f.endsWith('.html')  // the report needs its CSS and renders next to it: open it, do not save it alone
                  ? <a href={outputUrl(projectId, latest.version, f)} target="_blank" rel="noreferrer">{f}</a>
                  : <a href={outputUrl(projectId, latest.version, f)} download>{f}</a>}</li>
              ))}
              {latest.files.filter((f) => f.startsWith('renders/')).map((f) => (
                <li key={f}><a href={outputUrl(projectId, latest.version, f)} target="_blank" rel="noreferrer">{f.replace('renders/', '')}</a></li>
              ))}
            </ul>
          ) : <p className="helper">Belum ada build 3D. Save, lalu klik Build 3D.</p>}
        </section>
      </aside>
      <div className="editor__viewport">
        {notice && <InlineNotification kind={notice.kind} lowContrast title="" subtitle={notice.text} onClose={() => useInstallStore.getState().setNotice(null)} />}
        {view3d ? (
          <div className="editor__canvas">
            {latest?.files.includes('layout_installation.glb')
              ? <InstallViewer url={`${outputUrl(projectId, latest.version, 'layout_installation.glb')}?b=${latest.built_at}`} />
              : <p className="helper">Belum ada build 3D. Klik Build 3D setelah Save.</p>}
          </div>
        ) : (
          <div className="editor__canvas editor__canvas--plan">
            <InstallWorkspace projectId={projectId} backdrop={backdrop} drops={validation.drops} />
          </div>
        )}
      </div>
      <aside className="editor__props" aria-label="Properti">
        {tool === 'assist' ? <AssistPanel projectId={projectId} /> : <InstallPanels validation={validation} saveIssues={saveIssues} />}
      </aside>
    </div>
  )
}
