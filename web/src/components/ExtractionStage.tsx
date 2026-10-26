import {
  Button, InlineNotification, Modal, ProgressBar, StructuredListBody, StructuredListCell, StructuredListRow, StructuredListWrapper,
  TextInput,
} from '@carbon/react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useSaveProfile, useStartRun } from '../api/hooks'
import type { Run, Stage, ValidationIssue } from '../api/types'
import type { Spec } from '../types/spec'

interface Props {
  projectId: string
  run: Run
  n: number
  message?: string
}

interface InputDoc { prompt: string; params_final: Record<string, unknown> }

/** Stage 0-5 panels (PRD/08): parameters, working page, grid, candidates, rooms, validation. */
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
      {n === 3 && done && <CandidatesStage art={art} runId={run.run_id} projectId={projectId} />}
      {n === 4 && done && <RoomsStage art={art} runId={run.run_id} projectId={projectId} />}
      {n === 5 && done && <ValidateStage art={art} run={run} stage={stage} projectId={projectId} />}
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

interface Candidate {
  index: number
  params: { strategy: string; sauvola_k: number; t_min: number; t_max: number; l_fix: number }
  counts: { walls: number; doors: number; columns: number; stairs: number } | null
  wall_len_m: number
  low_conf: number
  error: string | null
}

function CandidatesStage({ art, runId, projectId }: { art: (p: string) => string; runId: string; projectId: string }) {
  const [selected, setSelected] = useState(0)
  const list = useQuery({
    queryKey: ['candidates', projectId, runId],
    queryFn: () => api.get<Candidate[]>(art('03_extract/candidates.json')),
  })
  if (!list.data) return null
  const failed = list.data.find((c) => c.index === selected)?.error
  return (
    <>
      <div className="candidate-scroll">
        <table className="candidate-table">
          <thead><tr><th>#</th><th>Strategi</th><th>k</th><th>t_min</th><th>L_fix</th><th>Dinding</th><th>Pintu</th><th>Kolom</th>
            <th>Tangga</th><th>Panjang (m)</th><th>Keyakinan rendah</th></tr></thead>
          <tbody>
            {list.data.map((c) => (
              <tr key={c.index} className={c.index === selected ? 'is-selected' : ''} onClick={() => setSelected(c.index)}>
                <td className="mono">
                  <label>
                    <input type="radio" name={`candidate-${runId}`} checked={c.index === selected}
                      onChange={() => setSelected(c.index)} aria-label={`Kandidat ${c.index}`} /> {c.index}
                  </label>
                </td>
                <td>{c.params.strategy}</td><td className="mono">{c.params.sauvola_k}</td>
                <td className="mono">{c.params.t_min}</td><td className="mono">{c.params.l_fix}</td>
                {c.error ? <td colSpan={6} className="helper">{c.error}</td> : (
                  <>
                    <td className="mono">{c.counts?.walls}</td><td className="mono">{c.counts?.doors}</td>
                    <td className="mono">{c.counts?.columns}</td><td className="mono">{c.counts?.stairs}</td>
                    <td className="mono">{c.wall_len_m}</td><td className="mono">{c.low_conf}</td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <figure>
        {failed
          ? <p className="helper">Kandidat {selected} gagal: {failed}</p>
          : <img src={art(`03_extract/candidates/${selected}/overlay.png`)} alt={`Kandidat ${selected}: elemen terdeteksi`} className="artifact-img" />}
        <figcaption className="helper">Biru: dinding · Oranye: dinding keyakinan rendah / kolom · Hijau: pintu · Ungu: tangga · Abu-abu: hatch dan simbol</figcaption>
      </figure>
    </>
  )
}

interface RoomCandidate { index: number; error: string | null; rooms: number; labelled: number; gross_area_m2: number }

function RoomsStage({ art, runId, projectId }: { art: (p: string) => string; runId: string; projectId: string }) {
  const [selected, setSelected] = useState(0)
  const list = useQuery({
    queryKey: ['rooms-candidates', projectId, runId],
    queryFn: () => api.get<RoomCandidate[]>(art('04_rooms/candidates.json')),
  })
  const current = list.data?.find((c) => c.index === selected) ?? list.data?.find((c) => !c.error)
  const spec = useQuery({
    queryKey: ['rooms-spec', projectId, runId, current?.index],
    queryFn: () => api.get<Pick<Spec, 'rooms'>>(art(`04_rooms/candidates/${current?.index}/spec.json`)),
    enabled: current !== undefined && !current.error,
  })
  if (!list.data) return null
  return (
    <>
      <div className="candidate-scroll">
        <table className="candidate-table">
          <thead><tr><th>#</th><th>Ruang</th><th>Berlabel</th><th>Luas kotor (m²)</th></tr></thead>
          <tbody>
            {list.data.map((c) => (
              <tr key={c.index} className={c.index === current?.index ? 'is-selected' : ''} onClick={() => setSelected(c.index)}>
                <td className="mono"><label><input type="radio" name={`rooms-${runId}`} checked={c.index === current?.index}
                  onChange={() => setSelected(c.index)} aria-label={`Kandidat ${c.index}`} /> {c.index}</label></td>
                {c.error ? <td colSpan={3} className="helper">{c.error}</td> : (
                  <><td className="mono">{c.rooms}</td><td className="mono">{c.labelled}</td><td className="mono">{c.gross_area_m2}</td></>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {current && !current.error && (
        <figure>
          <img src={art(`04_rooms/candidates/${current.index}/rooms.png`)} alt={`Ruang kandidat ${current.index}`} className="artifact-img" />
        </figure>
      )}
      {spec.data && (
        <div className="candidate-scroll">
          <table className="candidate-table" aria-label="Ruang">
            <thead><tr><th>ID</th><th>Nama</th><th>Tipe</th><th>Luas (m²)</th></tr></thead>
            <tbody>
              {(spec.data.rooms ?? []).map((r) => (
                <tr key={r.id}><td className="mono">{r.id}</td><td>{r.name || '—'}</td><td className="mono">{r.type}</td>
                  <td className="mono">{r.area_m2}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

interface Score { index: number; score: number; passed: boolean; ratios: Record<string, number>; errors: string[]; coverage: number }
interface Chosen { index: number; score: number; version: number }

function ValidateStage({ art, run, stage, projectId }: { art: (p: string) => string; run: Run; stage: Stage; projectId: string }) {
  const key = (name: string) => [name, projectId, run.run_id]
  const scores = useQuery({ queryKey: key('scores'), queryFn: () => api.get<Score[]>(art('05_validate/scores.json')) })
  const chosen = useQuery({ queryKey: key('chosen'), queryFn: () => api.get<Chosen>(art('05_validate/chosen.json')),
    enabled: !!stage.metrics.version })
  const issues = useQuery({ queryKey: key('issues'), queryFn: () => api.get<ValidationIssue[]>(art('05_validate/issues.json')),
    enabled: !!stage.metrics.version })
  const save = useSaveProfile()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [saved, setSaved] = useState<string | null>(null)
  const best = scores.data?.find((s) => s.index === chosen.data?.index)
  return (
    <>
      {chosen.data && (
        <p className="big-number">
          <span className="mono">{chosen.data.score.toFixed(3)}</span>
          <span className="helper"> skor validator · kandidat {chosen.data.index} · spec v{chosen.data.version}</span>
        </p>
      )}
      {stage.warnings.map((w) => <p key={w} className="helper warning-line">{w}</p>)}
      {best && Object.entries(best.ratios).map(([code, ratio]) => (
        <ProgressBar key={code} label={code} value={Math.round((1 - ratio) * 100)} max={100} size="small"
          helperText={`${Math.round((1 - ratio) * 100)}% lolos`} />
      ))}
      {issues.data && (
        <div className="candidate-scroll">
          <table className="candidate-table" aria-label="Masalah validator">
            <thead><tr><th>Kode</th><th>Severity</th><th>Elemen</th><th>Pesan</th></tr></thead>
            <tbody>
              {issues.data.map((i, k) => (
                <tr key={k}>
                  <td className="mono">{i.code}</td><td>{i.severity}</td>
                  <td className="mono">{(i.element_ids ?? []).map((id) => (
                    <Link key={id} to={`?tab=review&focus=${id}`} className="issue-link">{id}</Link>))}</td>
                  <td>{i.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {stage.status === 'succeeded' && (
        <Button kind="tertiary" size="sm" onClick={() => setOpen(true)}>Simpan sebagai profile</Button>
      )}
      {saved && <InlineNotification kind="success" lowContrast title="Profile tersimpan" subtitle={saved} onClose={() => setSaved(null)} />}
      <Modal open={open} modalHeading="Simpan sebagai profile" primaryButtonText="Simpan" secondaryButtonText="Batal"
        primaryButtonDisabled={!name.trim() || save.isPending} onRequestClose={() => setOpen(false)}
        onRequestSubmit={() => save.mutate({ name: name.trim(), from_run: `${projectId}/${run.run_id}` },
          { onSuccess: (p) => { setSaved(p.profile_id); setOpen(false) } })}>
        <TextInput id="profile-name" labelText="Nama profile" value={name} onChange={(e) => setName(e.target.value)} />
      </Modal>
    </>
  )
}
