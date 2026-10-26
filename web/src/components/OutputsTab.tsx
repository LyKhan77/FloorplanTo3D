import { Button, ClickableTile, Dropdown, Link, Tile } from '@carbon/react'
import { Download } from '@carbon/icons-react'
import { useState } from 'react'
import { outputsBase } from '../api/client'
import { useOutputs } from '../api/hooks'
import { formatBytes } from '../lib/format'

export function OutputsTab({ projectId }: { projectId: string }) {
  const { data: outputs = [] } = useOutputs(projectId)
  const [picked, setPicked] = useState<number | null>(null)
  if (!outputs.length) return <p className="helper tab-pad">Belum ada output. Tekan Regenerate setelah spec tersedia.</p>
  const current = outputs.find((o) => o.version === picked) ?? outputs[0]
  const base = outputsBase(projectId, current.version)
  return (
    <div className="tab-pad">
      <div className="outputs-head">
        <Dropdown id="out-version" titleText="Versi" label="Versi" items={outputs.map((o) => o.version)}
          itemToString={(v) => (v === null ? '' : `v${v}`)} selectedItem={current.version} onChange={({ selectedItem }) => setPicked(selectedItem ?? null)} />
        <Button renderIcon={Download} href={`${base}/bundle.zip`}>Unduh semua (zip)</Button>
      </div>
      <div className="file-grid">
        {current.files.map((f) => (
          <Tile key={f.name} className="file-card">
            <span className="mono">{f.name}</span>
            <span className="helper">{formatBytes(f.bytes)}</span>
            <Link href={`${base}/${f.name}`} download={f.name} renderIcon={Download}>Unduh</Link>
          </Tile>
        ))}
      </div>
      {current.files.some((f) => f.name === 'report.html') && (
        <iframe title="Dokumen map 3D" src={`${base}/report.html`} className="report-frame" />
      )}
      <h2 className="section-title">Render</h2>
      <div className="render-grid">
        {current.renders.filter((r) => r.endsWith('.png')).map((r) => (
          <ClickableTile key={r} href={`${base}/renders/${r}`} className="render-card">
            <img src={`${base}/renders/${r}`} alt={`Render ${r}`} loading="lazy" />
            <span className="mono helper">{r}</span>
          </ClickableTile>
        ))}
      </div>
    </div>
  )
}
