import { Button, InlineNotification, Modal, StructuredListBody, StructuredListCell, StructuredListRow, StructuredListWrapper, TextInput } from '@carbon/react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { useStartRun } from '../api/hooks'
import type { Run } from '../api/types'

interface Props {
  projectId: string
  run: Run
  n: number
  message?: string
}

interface InputDoc { prompt: string; params_final: Record<string, unknown> }

/** Stage 0-2 panels (PRD/08): parameters, working page, grid overlay with scale and manual-scale rerun. */
export function ExtractionStage({ projectId, run, n, message }: Props) {
  const stage = run.stages[n]
  const art = (path: string) => `/api/projects/${projectId}/runs/${run.run_id}/artifacts/${path}`
  const m = stage.metrics as Record<string, number | string | null | undefined>
  const done = stage.status === 'succeeded' || stage.status === 'needs_attention'
  const input = useQuery({
    queryKey: ['stage-input', projectId, run.run_id],
    queryFn: () => api.get<InputDoc>(art('00_input/input.json')),
    enabled: n === 0 && stage.status === 'succeeded',
  })
  return (
    <div className="extraction-stage">
      {stage.status === 'needs_attention' && message && (
        <InlineNotification kind="error" lowContrast hideCloseButton title="Perlu perhatian" subtitle={message} />
      )}
      {n === 0 && input.data && (
        <>
          {input.data.prompt && <p className="mono">{input.data.prompt}</p>}
          <StructuredListWrapper isCondensed aria-label="Parameter akhir">
            <StructuredListBody>
              {Object.entries(input.data.params_final).map(([k, v]) => (
                <StructuredListRow key={k}><StructuredListCell className="mono">{k}</StructuredListCell>
                  <StructuredListCell className="mono">{String(v)}</StructuredListCell></StructuredListRow>
              ))}
            </StructuredListBody>
          </StructuredListWrapper>
          {!Object.keys(input.data.params_final).length && <p className="helper">Tanpa parameter; dipakai nilai default.</p>}
        </>
      )}
      {n === 1 && done && (
        <figure>
          <img src={art('01_preprocess/page.png')} alt="Gambar kerja setelah preprocess" className="artifact-img" />
          <figcaption className="helper mono">
            {m.work_w} × {m.work_h} px · upscale {m.upscale}× · deskew {m.deskew_deg}°
          </figcaption>
        </figure>
      )}
      {n === 2 && done && <GridStage projectId={projectId} run={run} art={art} metrics={m} warnings={stage.warnings}
        attention={stage.status === 'needs_attention'} />}
    </div>
  )
}

function GridStage({ projectId, art, metrics: m, warnings, attention }: {
  projectId: string; run: Run; art: (p: string) => string; metrics: Record<string, number | string | null | undefined>
  warnings: string[]; attention: boolean
}) {
  const start = useStartRun(projectId)
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState('')
  const [touched, setTouched] = useState(false)
  const mm = Number(value)
  const valid = value.trim() !== '' && Number.isFinite(mm) && mm > 0
  return (
    <>
      {typeof m.mm_per_px === 'number' && (
        <p className="mono">{m.mm_per_px.toFixed(3)} mm/px · {m.scale_source} · {m.axes_v} × {m.axes_h} sumbu · residu maks {m.residual_max_pct}%</p>
      )}
      {warnings.map((w) => <InlineNotification key={w} kind="warning" lowContrast hideCloseButton title="Peringatan" subtitle={w} />)}
      <figure>
        <img src={art('02_grid/overlay.png')} alt="Sumbu grid dan dimensi yang dipakai untuk skala" className="artifact-img" />
        <figcaption className="helper">Magenta: sumbu grid · Hijau: dimensi dipakai · Merah: dimensi dibuang</figcaption>
      </figure>
      <Button kind={attention ? 'primary' : 'tertiary'} size="sm" onClick={() => setOpen(true)}>Isi skala manual</Button>
      <Modal open={open} modalHeading="Skala manual" primaryButtonText="Jalankan" secondaryButtonText="Batal"
        onRequestClose={() => setOpen(false)}
        onRequestSubmit={() => {
          setTouched(true)
          if (!valid) return
          start.mutate({ kind: 'from_stage', from_stage: 2, params_override: { mm_per_px: mm } })
          setOpen(false)
        }}>
        <TextInput id="manual-scale" labelText="Skala manual (mm per px)" value={value} inputMode="decimal"
          helperText="mm per piksel gambar asli; tahap 2 dijalankan ulang" onChange={(e) => setValue(e.target.value)}
          invalid={touched && !valid} invalidText="Isi angka lebih dari 0" />
      </Modal>
    </>
  )
}
