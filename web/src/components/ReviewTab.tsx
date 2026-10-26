import { InlineNotification } from '@carbon/react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Run, ValidationIssue } from '../api/types'
import { OverlayViewer } from './OverlayViewer'

const LAYERS = [['rooms', 'Ruang'], ['walls', 'Dinding'], ['doors', 'Pintu'], ['columns', 'Kolom']] as const

/** Review tab (PRD/08): numbered overlay of the latest extracted spec with layer toggles, and the validator
 * issues left. Strata decisions arrive in M6. */
export function ReviewTab({ projectId, runs }: { projectId: string; runs: Run[] }) {
  const [params] = useSearchParams()
  const focus = params.get('focus')
  const run = [...runs].sort((a, b) => b.created_at.localeCompare(a.created_at) || b.run_id.localeCompare(a.run_id))
    .find((r) => r.stages[5]?.metrics?.version)
  const art = (path: string) => `/api/projects/${projectId}/runs/${run?.run_id}/artifacts/${path}`
  const issues = useQuery({
    queryKey: ['review-issues', projectId, run?.run_id],
    queryFn: () => api.get<ValidationIssue[]>(art('05_validate/issues.json')),
    enabled: !!run,
  })
  if (!run) return <p className="helper">Belum ada hasil validasi</p>
  return (
    <div className="review-grid">
      <OverlayViewer src={art('01_preprocess/page.png')} alt={`Overlay bernomor spec v${run.stages[5].metrics.version}`}
        layers={LAYERS.map(([id, label]) => ({ id, label, src: art(`05_validate/layers/${id}.png`), visible: true }))} />
      <div>
        {run.stages[6]?.status === 'skipped' && (
          <InlineNotification kind="info" lowContrast hideCloseButton title="Strata"
            subtitle="Review Strata tersedia di M6; tahap 6 dilewati." />
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
