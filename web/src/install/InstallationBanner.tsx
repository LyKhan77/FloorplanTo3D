import { Button, InlineNotification } from '@carbon/react'
import { type QueryClient, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { ProjectDetail } from '../api/types'
import { rebaseInstallation, startInstallation } from './api'
import { StartInstallationDialog, type StartValues } from './StartInstallationDialog'
import { useInstallStore } from './store'

function refreshInstallation(qc: QueryClient, pid: string) {
  for (const k of ['project', 'installation']) qc.invalidateQueries({ queryKey: [k, pid] })
  qc.invalidateQueries({ queryKey: ['projects'] })
}

/** The installation is pinned to an older layout version: say so and offer Rebase (project page and mode Instalasi). */
export function RebaseNotice({ project }: { project: ProjectDetail }) {
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inst = project.installation
  // a rebase writes a new version: pending installation work would then fail to save, so it waits
  const pending = useInstallStore((s) => s.projectId === project.project_id && s.ops.length > 0)
  const rebase = async () => {
    setBusy(true)
    try {
      const r = await rebaseInstallation(project.project_id)
      setResult(`Rebase ke v${project.head}: ${r.issues.length ? `${r.issues.length} masalah, cek panel Masalah di mode Instalasi` : 'tanpa masalah'}`)
      refreshInstallation(qc, project.project_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      {inst?.layout_changed && (
        <div className="install-rebase">
          <InlineNotification kind="warning" lowContrast hideCloseButton title="Layout berubah"
            subtitle={`Layout berubah (v${inst.layout_version} → v${project.head}): build 3D instalasi masih memakai layout v${inst.layout_version}.${pending ? ' Save pekerjaan instalasi dulu.' : ''}`} />
          <Button size="sm" kind="tertiary" disabled={pending || busy} onClick={() => void rebase()}>Rebase</Button>
        </div>
      )}
      {result && <p className="helper" role="status">{result}</p>}
      {error && <p className="helper" role="alert">{error}</p>}
    </>
  )
}

/** Project page (M12a): start the optional installation layer once the layout has outputs; flag a layout that moved on. */
export function InstallationBanner({ project, onStarted }: { project: ProjectDetail; wallHeight?: number; onStarted(): void }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inst = project.installation
  const refresh = () => refreshInstallation(qc, project.project_id)
  const start = async (v: StartValues) => {
    setBusy(true)
    try {
      await startInstallation(project.project_id, v)
      setOpen(false)
      refresh()
      onStarted()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }
  const param = (k: string) => (typeof project.params?.[k] === 'number' ? (project.params[k] as number) : null)
  return (
    <>
      {!inst && <Button kind="tertiary" onClick={() => setOpen(true)}>Mulai instalasi</Button>}
      <RebaseNotice project={project} />
      {error && <p className="helper" role="alert">{error}</p>}
      {open && <StartInstallationDialog ceiling={param('ceiling_height')} raised={param('raised_floor_height')} busy={busy}
        onSubmit={(v) => void start(v)} onClose={() => setOpen(false)} />}
    </>
  )
}
