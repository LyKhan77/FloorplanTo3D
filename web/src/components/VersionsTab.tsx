import { ActionableNotification, Button, Dropdown, Tag, Tooltip } from '@carbon/react'
import { useState } from 'react'
import { useRegenerate, useSpecDiff, useSpecs } from '../api/hooks'
import { summarizeDiff } from '../lib/diff'
import { formatTime } from '../lib/format'

const SOURCE_TAG: Record<string, 'blue' | 'purple' | 'teal' | 'gray' | 'cyan'> = {
  pipeline: 'blue', llm: 'purple', editor: 'teal', manual: 'gray', migration: 'cyan',
}

export function VersionsTab({ projectId }: { projectId: string }) {
  const { data: versions = [] } = useSpecs(projectId)
  const regenerate = useRegenerate(projectId)
  const latest = versions.at(-1)?.version ?? null
  const [from, setFrom] = useState<number | null>(null)
  const [to, setTo] = useState<number | null>(null)
  const a = from ?? (versions.length > 1 ? versions[versions.length - 2].version : null)
  const b = to ?? latest
  const { data: diff } = useSpecDiff(projectId, a, b)
  if (!versions.length) return <p className="helper tab-pad">Belum ada versi spec.</p>
  const nums = versions.map((v) => v.version)
  const reused = regenerate.data?.reused ? regenerate.variables : null
  return (
    <div className="tab-pad">
      {typeof reused === 'number' && (
        <ActionableNotification kind="info" lowContrast inline hideCloseButton title="Output sudah ada"
          subtitle={`output v${reused} dipakai ulang. Bangun ulang untuk memakai builder dan pemeriksaan terbaru.`}
          actionButtonLabel="Bangun ulang" onActionButtonClick={() => regenerate.mutate({ version: reused, force: true })} />
      )}
      <table className="cds--data-table cds--data-table--compact versions-table">
        <thead><tr><th>Versi</th><th>Sumber</th><th>Waktu</th><th>Pesan</th><th>Run</th><th>Output</th><th aria-label="Aksi" /></tr></thead>
        <tbody>
          {versions.slice().reverse().map((v) => (
            <tr key={v.version}>
              <td className="mono">v{v.version}</td>
              <td><Tag type={SOURCE_TAG[v.source] ?? 'gray'} size="sm">{v.source}</Tag></td>
              <td>{formatTime(v.created_at)}</td>
              <td>{v.message || '—'}</td>
              <td className="mono">{v.run_id ?? '—'}</td>
              <td>{v.has_outputs ? 'tersedia' : '—'}</td>
              <td className="versions-actions">
                <Button kind="ghost" size="sm" onClick={() => regenerate.mutate(v.version)}>Regenerate versi ini</Button>
                <Tooltip label="Tersedia di M4 (editor)" align="left">
                  <Button kind="ghost" size="sm" disabled>Jadikan basis editor</Button>
                </Tooltip>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {nums.length > 1 && (
        <div className="diff-box">
          <h2 className="section-title">Diff ringkas</h2>
          <div className="diff-pickers">
            <Dropdown id="diff-from" titleText="Dari" label="Dari" items={nums} itemToString={(n) => (n === null ? '' : `v${n}`)}
              selectedItem={a} onChange={({ selectedItem }) => setFrom(selectedItem ?? null)} />
            <Dropdown id="diff-to" titleText="Ke" label="Ke" items={nums} itemToString={(n) => (n === null ? '' : `v${n}`)}
              selectedItem={b} onChange={({ selectedItem }) => setTo(selectedItem ?? null)} />
          </div>
          {diff && (
            <>
              <ul className="diff-summary">{(summarizeDiff(diff).length ? summarizeDiff(diff) : ['Tidak ada perubahan elemen']).map((l) => <li key={l} className="mono">{l}</li>)}</ul>
              <h3 className="helper">Ops</h3>
              <ul className="diff-ops mono">{(diff.ops ?? []).map((o, i) => <li key={i}>{o.op} {o.id ?? ''} {o.reason ? `— ${o.reason}` : ''}</li>)}</ul>
            </>
          )}
        </div>
      )}
    </div>
  )
}
