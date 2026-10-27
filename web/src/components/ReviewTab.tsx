import { InlineNotification, Tag } from '@carbon/react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { LlmDecision, Run, ValidationIssue } from '../api/types'
import { parseTranscript, strataSummary, verdictText } from '../lib/strata'
import { OverlayViewer } from './OverlayViewer'

const DECISION_TAG: Record<LlmDecision['decision'], 'green' | 'red' | 'gray' | 'blue'> = {
  accepted: 'green', rejected: 'red', no_consensus: 'gray', invalid_output: 'gray', no_change: 'blue',
}

const LAYERS = [['rooms', 'Ruang'], ['walls', 'Dinding'], ['doors', 'Pintu'], ['columns', 'Kolom']] as const

/** Review tab (PRD/08): numbered overlay of the latest extracted spec with layer toggles, the validator issues
 * left, and Strata's stage-6 decisions with the crop and the raw answers behind each one (PRD/05 §9). */
export function ReviewTab({ projectId, runs }: { projectId: string; runs: Run[] }) {
  const [params, setParams] = useSearchParams()
  const focus = params.get('focus')
  const [picked, setPicked] = useState<string | null>(null)
  const run = [...runs].sort((a, b) => b.created_at.localeCompare(a.created_at) || b.run_id.localeCompare(a.run_id))
    .find((r) => r.stages[5]?.metrics?.version)
  const art = (path: string) => `/api/projects/${projectId}/runs/${run?.run_id}/artifacts/${path}`
  const issues = useQuery({
    queryKey: ['review-issues', projectId, run?.run_id],
    queryFn: () => api.get<ValidationIssue[]>(art('05_validate/issues.json')),
    enabled: !!run,
  })
  const review = run?.stages[6]
  const reviewed = review?.status === 'succeeded'
  const decisions = useQuery({
    queryKey: ['review-decisions', projectId, run?.run_id],
    queryFn: () => api.get<LlmDecision[]>(art('06_review/decisions.json')),
    enabled: !!run && reviewed,
  })
  const transcript = useQuery({
    queryKey: ['review-transcript', projectId, run?.run_id],
    queryFn: async () => parseTranscript(await api.text(art('06_review/transcript.jsonl'))),
    enabled: !!run && reviewed,
  })
  if (!run) return <p className="helper">Belum ada hasil validasi</p>
  const pick = (element: string) => {
    setPicked(element)
    setParams((p) => { p.set('focus', element); return p }, { replace: true })
  }
  const votes = (transcript.data ?? []).filter((l) => l.element === picked)
  const hasCrop = votes.some((l) => l.request?.messages_ref)
  return (
    <div className="review-grid">
      <OverlayViewer src={art('01_preprocess/page.png')} alt={`Overlay bernomor spec v${run.stages[5].metrics.version}`}
        layers={LAYERS.map(([id, label]) => ({ id, label, src: art(`05_validate/layers/${id}.png`), visible: true }))} />
      <div>
        {review?.status === 'skipped' && (
          <InlineNotification kind="info" lowContrast hideCloseButton title="Strata" subtitle={strataSummary(review)} />
        )}
        {reviewed && (
          <>
            <h3 className="section-title">Keputusan Strata</h3>
            <p className="helper">{strataSummary(review)}</p>
            <div className="candidate-scroll">
              <table className="candidate-table" aria-label="Keputusan Strata">
                <thead><tr><th>Elemen</th><th>Tugas</th><th>Jawaban</th><th>Keputusan</th><th>Skor</th></tr></thead>
                <tbody>
                  {(decisions.data ?? []).map((d, k) => (
                    <tr key={k} className={picked === d.element ? 'is-focused' : ''} onClick={() => pick(d.element)}
                      style={{ cursor: 'pointer' }}>
                      <td className="mono">{d.element}</td><td>{d.task}</td><td>{verdictText(d.verdict)}</td>
                      <td><Tag size="sm" type={DECISION_TAG[d.decision]}>{d.decision}</Tag>{d.reason ? ` ${d.reason}` : ''}</td>
                      <td className="mono">{d.score_before.toFixed(3)} → {d.score_after.toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {picked && (
              <div className="strata-detail">
                {hasCrop && (
                  <div className="strata-detail__images">
                    <img src={art(`06_review/crops/${picked}_v1.png`)} alt={`Crop ${picked}`} />
                    <img src={art(`06_review/crops/${picked}_ctx.png`)} alt={`Konteks ${picked}`} />
                  </div>
                )}
                {votes.map((l, k) => (
                  <pre key={k} className="log-tail mono" aria-label={`Respons mentah suara ${l.vote ?? k + 1}`}>
                    {l.response?.raw || l.response?.error || '—'}
                  </pre>
                ))}
              </div>
            )}
          </>
        )}
        <div className="candidate-scroll">
          <table className="candidate-table" aria-label="Masalah validator">
            <thead><tr><th>Kode</th><th>Severity</th><th>Elemen</th><th>Pesan</th></tr></thead>
            <tbody>
              {(issues.data ?? []).map((i, k) => (
                <tr key={k} className={focus && i.element_ids?.includes(focus) ? 'is-focused' : ''}
                  aria-current={focus && i.element_ids?.includes(focus) ? 'true' : undefined}>
                  <td className="mono">{i.code}</td><td>{i.severity}</td>
                  <td className="mono">{(i.element_ids ?? []).join(', ')}</td><td>{i.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
