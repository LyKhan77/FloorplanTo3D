import { Tile } from '@carbon/react'
import { useConfig, useHealth } from '../api/hooks'
import { StatusTag } from '../components/StatusTag'

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return <><dt className="helper">{k}</dt><dd className="mono">{v}</dd></>
}

export function SystemPage() {
  const { data: h } = useHealth()
  const { data: c } = useConfig()
  return (
    <>
      <h1 className="page-title">System</h1>
      <div className="system-grid">
        <Tile>
          <h2 className="section-title">Strata</h2>
          <dl className="kv">
            <Row k="Status" v={h ? <StatusTag status={h.strata.ok ? 'succeeded' : 'failed'} /> : '—'} />
            <Row k="Mode" v={h?.strata.status ?? '—'} />
            <Row k="Latensi" v={h?.strata.latency_ms != null ? `${h.strata.latency_ms} ms` : '—'} />
            <Row k="Base URL" v={c?.strata_base_url ?? '—'} />
            <Row k="Model" v={c?.strata_model ?? '—'} />
            <Row k="Tugas LLM aktif" v={c?.llm_tasks_enabled.length ? c.llm_tasks_enabled.join(', ') : 'tidak ada'} />
          </dl>
        </Tile>
        <Tile>
          <h2 className="section-title">Blender</h2>
          <dl className="kv">
            <Row k="Status" v={h ? <StatusTag status={h.blender.ok ? (h.blender.busy ? 'running' : 'succeeded') : 'failed'} /> : '—'} />
            <Row k="Versi" v={h?.blender.version ?? '—'} />
            <Row k="Path" v={c?.blender_bin ?? '—'} />
          </dl>
        </Tile>
        <Tile>
          <h2 className="section-title">Antrean</h2>
          <dl className="kv">
            <Row k="Menunggu" v={h?.queue.waiting ?? '—'} />
            <Row k="Berjalan" v={h?.queue.running.length ? h.queue.running.join(', ') : '—'} />
          </dl>
        </Tile>
        <Tile>
          <h2 className="section-title">Aplikasi</h2>
          <dl className="kv">
            <Row k="Versi kode" v={c?.code_version ?? '—'} />
            <Row k="Skema spec" v={c?.schema_version ?? '—'} />
          </dl>
        </Tile>
      </div>
    </>
  )
}
