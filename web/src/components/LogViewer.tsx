import { Button, Dropdown, FilterableMultiSelect, MultiSelect, TextInput, Toggle } from '@carbon/react'
import { Download } from '@carbon/icons-react'
import { useMemo, useState } from 'react'
import { Virtuoso } from 'react-virtuoso'
import type { ApiEvent, Run } from '../api/types'
import { filterEvents, formatLogLine } from '../lib/logs'
import { stageLabel } from '../lib/runState'

const LEVELS = ['debug', 'info', 'warn', 'error']
const STAGES = Array.from({ length: 11 }, (_, n) => ({ id: n, text: `${n} · ${stageLabel(n)}` }))

export function LogViewer({ projectId, runs, events }: { projectId: string; runs: Run[]; events: ApiEvent[] }) {
  const [runId, setRunId] = useState<string | null>(runs[0]?.run_id ?? null)
  const [stages, setStages] = useState<number[]>([])
  const [levels, setLevels] = useState<string[]>(['info', 'warn', 'error'])
  const [q, setQ] = useState('')
  const [follow, setFollow] = useState(true)
  const rows = useMemo(() => filterEvents(events, { runId, stages, levels, q }), [events, runId, stages, levels, q])
  const runItems = [{ id: null, text: 'Semua run' }, ...runs.map((r) => ({ id: r.run_id, text: `${r.run_id} · ${r.kind}` }))]

  return (
    <div className="log-viewer">
      <div className="log-toolbar">
        <Dropdown id="log-run" titleText="Run" label="Run" items={runItems} itemToString={(i) => i?.text ?? ''}
          selectedItem={runItems.find((i) => i.id === runId) ?? runItems[0]} onChange={({ selectedItem }) => setRunId(selectedItem?.id ?? null)} />
        <FilterableMultiSelect id="log-stage" titleText="Tahap" placeholder="Semua tahap" items={STAGES} itemToString={(i) => i?.text ?? ''}
          onChange={({ selectedItems }) => setStages((selectedItems ?? []).map((i) => i.id))} />
        <MultiSelect id="log-level" titleText="Level" label="Level" items={LEVELS} initialSelectedItems={levels}
          onChange={({ selectedItems }) => setLevels(selectedItems ?? [])} />
        <TextInput id="log-q" labelText="Cari" placeholder="Teks" value={q} onChange={(e) => setQ(e.target.value)} />
        <Toggle id="log-follow" labelText="Ikuti" toggled={follow} onToggle={setFollow} size="sm" />
        <Button kind="ghost" size="sm" renderIcon={Download} href={`/api/projects/${projectId}/events.jsonl${runId ? `?run_id=${runId}` : ''}`}>
          Unduh
        </Button>
      </div>
      <div className="log-list mono" role="log" aria-live="polite" aria-label="Log pipeline">
        <Virtuoso data={rows} followOutput={follow ? 'auto' : false} initialTopMostItemIndex={Math.max(rows.length - 1, 0)}
          itemContent={(_i, e) => {
            const l = formatLogLine(e)
            return (
              <div className="log-line">
                <span className="log-time">{l.time}</span>
                <span className="log-stage">{l.stage}</span>
                <span className={`log-level log-level--${e.level}`}>{l.level.padEnd(5)}</span>
                <span className="log-msg">{l.msg}</span>
              </div>
            )
          }} />
      </div>
    </div>
  )
}
