import { Button, InlineNotification, ProgressBar, Tile } from '@carbon/react'
import { Download, Launch } from '@carbon/icons-react'
import { useQuery } from '@tanstack/react-query'
import { api, outputsBase } from '../api/client'
import { useOutputs } from '../api/hooks'
import type { ApiEvent, Run } from '../api/types'
import { formatBytes, formatDuration } from '../lib/format'
import { formatLogLine } from '../lib/logs'
import { stageLabel } from '../lib/runState'
import { StatusTag } from './StatusTag'

interface Props {
  projectId: string
  run: Run
  n: number
  events: ApiEvent[]
  onOpenEditor: () => void
}

interface Verify {
  iou: number | null
  iou_threshold: number
  status: string
  warnings: string[]
  glb_check: { pass: boolean; max_err_mm: number | null; checked: number }
  grid_check: { status?: string; pass?: boolean; max_err_mm?: number }
}

export function StagePanel({ projectId, run, n, events, onOpenEditor }: Props) {
  const stage = run.stages[n]
  const out = outputsBase(projectId, run.version)
  const { data: outputs } = useOutputs(projectId)
  const published = outputs?.find((o) => o.version === run.version)
  const verify = useQuery({
    queryKey: ['verify', projectId, run.run_id, run.version],
    queryFn: () => api.get<Verify>(`/api/projects/${projectId}/runs/${run.run_id}/artifacts/07_build/work/verify.json`),
    enabled: n === 8 && run.stages[8].status !== 'pending' && run.stages[8].status !== 'running',
  })
  const logs = events.filter((e) => e.run_id === run.run_id && e.stage === n && e.type === 'stage.log').slice(-20)
  const messages = events.filter((e) => e.run_id === run.run_id && e.stage === n && e.type === 'stage.log' && e.level !== 'debug')

  return (
    <Tile className="stage-panel">
      <div className="stage-panel__head">
        <h2><span className="mono">{n}</span> · {stageLabel(n)}</h2>
        <span className="stage-panel__status"><StatusTag status={stage.status} warning={stage.status === 'succeeded' && stage.warnings.length > 0} />
          <span className="mono">{formatDuration(stage.duration_ms)}</span></span>
      </div>

      {n <= 6 && (
        <p className="helper">{messages.at(-1)?.msg ?? (n === 6 ? 'Review Strata tersedia di M6.' : 'Ekstraksi otomatis tersedia di M5.')}</p>
      )}

      {n === 7 && (
        <>
          {stage.status === 'running' && <ProgressBar label="Build Blender" value={stage.progress ?? 0} max={100} />}
          <pre className="log-tail mono" aria-label="Log tahap build">{logs.map((e) => formatLogLine(e).msg).join('\n') || '—'}</pre>
          {published && (
            <table className="file-table"><tbody>
              {published.files.map((f) => <tr key={f.name}><td className="mono">{f.name}</td><td className="mono">{formatBytes(f.bytes)}</td></tr>)}
            </tbody></table>
          )}
        </>
      )}

      {n === 8 && verify.data && (
        <div className="verify">
          <div className="verify__iou">
            <span className="verify__value mono">{verify.data.iou ?? '—'}</span>
            <span className="helper">IoU top-down · ambang {verify.data.iou_threshold}</span>
          </div>
          <p>Cek glb 1:1: {verify.data.glb_check.pass ? 'lulus' : 'gagal'} (galat maks <span className="mono">{verify.data.glb_check.max_err_mm} mm</span>, {verify.data.glb_check.checked} dinding) · Cek grid: {verify.data.grid_check.status ?? (verify.data.grid_check.pass ? 'lulus' : 'gagal')}</p>
          {verify.data.warnings.map((w) => <InlineNotification key={w} kind="warning" lowContrast hideCloseButton title="Peringatan" subtitle={w} />)}
          {published?.files.some((f) => f.name === 'iou_mask.png') && (
            <figure>
              <img src={`${out}/iou_mask.png`} alt="Perbandingan mask dinding model dan denah" className="artifact-img" />
              <figcaption className="helper">Hijau: cocok · Merah: hanya di denah · Biru: hanya di model</figcaption>
            </figure>
          )}
        </div>
      )}

      {n === 9 && published && (
        <>
          <Button kind="tertiary" size="sm" renderIcon={Download} href={`${out}/report.pdf`}>Unduh PDF</Button>
          <iframe title="Dokumen map 3D" src={`${out}/report.html`} className="report-frame" />
        </>
      )}

      {n === 10 && stage.status === 'succeeded' && (
        <Button renderIcon={Launch} onClick={onOpenEditor}>Buka editor</Button>
      )}
      {stage.status === 'failed' && run.error && <InlineNotification kind="error" lowContrast hideCloseButton title="Gagal" subtitle={run.error} />}
    </Tile>
  )
}
