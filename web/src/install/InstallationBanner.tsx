import { ActionableNotification, Button } from '@carbon/react'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { ProjectDetail } from '../api/types'
import { rebaseInstallation, startInstallation } from './api'
import { StartInstallationDialog, type StartValues } from './StartInstallationDialog'

/** Project page (M12a): start the optional installation layer once the layout has outputs; flag a layout that moved on. */
export function InstallationBanner({ project, onStarted }: { project: ProjectDetail; wallHeight?: number; onStarted(): void }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inst = project.installation
  const refresh = () => {
    for (const k of ['project', 'installation']) qc.invalidateQueries({ queryKey: [k, project.project_id] })
    qc.invalidateQueries({ queryKey: ['projects'] })
  }
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
      {!inst && project.outputs.length > 0 && <Button kind="tertiary" onClick={() => setOpen(true)}>Mulai instalasi</Button>}
      {inst?.layout_changed && (
        <ActionableNotification kind="warning" lowContrast inline hideCloseButton title="Layout berubah"
          subtitle={`Layout berubah (v${inst.layout_version} → v${project.head}): cek instalasi.`} actionButtonLabel="Rebase"
          onActionButtonClick={() => { void rebaseInstallation(project.project_id).then(refresh).catch((e) => setError(String(e))) }} />
      )}
      {error && <p className="helper" role="alert">{error}</p>}
      {open && <StartInstallationDialog ceiling={param('ceiling_height')} raised={param('raised_floor_height')} busy={busy}
        onSubmit={(v) => void start(v)} onClose={() => setOpen(false)} />}
    </>
  )
}
