import { Button, Modal } from '@carbon/react'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../../api/client'
import { useEditorStore } from '../store'

/** M8: a run paused for review goes on to stages 6-10 with the corrected spec; unsaved edits are saved first. */
export function ApproveButton({ projectId, runId, tasksLeft, save }: {
  projectId: string; runId: string; tasksLeft: number; save: (message?: string) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [, setParams] = useSearchParams()
  const qc = useQueryClient()
  const approve = async () => {
    setBusy(true)
    try {
      if (useEditorStore.getState().ops.length) {
        await save('Review: koreksi sebelum build 3D')
        if (useEditorStore.getState().ops.length) return  // the save failed; its notice says why
      }
      await api.post(`/api/projects/${projectId}/runs/${runId}/continue`, { accept_low_score: false })
      for (const k of ['project', 'runs']) qc.invalidateQueries({ queryKey: [k, projectId] })
      setOpen(false)
      setParams({ tab: 'pipeline' })
    } catch (e) {
      useEditorStore.getState().setNotice({ kind: 'error', text: `Gagal melanjutkan: ${String(e)}` })
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <Button size="sm" kind="primary" onClick={() => setOpen(true)}>Setujui &amp; build 3D</Button>
      <Modal open={open} modalHeading="Setujui dan build 3D?" primaryButtonText="Setujui" secondaryButtonText="Kembali"
        primaryButtonDisabled={busy} onRequestClose={() => setOpen(false)} onRequestSubmit={() => void approve()}>
        <p>Koreksi disimpan sebagai versi baru, lalu tahap 6–10 (review Strata, build, verifikasi, dokumen) berjalan.</p>
        {tasksLeft > 0 && <p className="helper">{tasksLeft} tugas review belum selesai; build tetap jalan dan sisanya tercatat sebagai warning.</p>}
      </Modal>
    </>
  )
}
