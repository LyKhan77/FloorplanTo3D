import { Dropdown } from '@carbon/react'
import type { Run } from '../api/types'
import { formatTime } from '../lib/format'
import { statusText } from '../lib/runState'

const kind = (r: Run) => (r.kind === 'full' ? 'Pipeline penuh' : r.kind === 'regenerate' ? 'Regenerate' : `Dari tahap ${r.from_stage}`)

/** Pipeline tab: every run of the project, newest first; an approve or regenerate run skips the extraction stages,
 *  whose results stay in the earlier run. */
export function RunPicker({ runs, value, onChange }: { runs: Run[]; value: string | null; onChange(runId: string): void }) {
  const label = (r: Run | null) => r ? `${formatTime(r.created_at)} · ${kind(r)} · ${statusText(r.status)}${r === runs[0] ? ' · terbaru' : ''}` : ''
  return (
    <Dropdown id="run-picker" className="run-picker" titleText="Run" label="Pilih run" size="sm" items={runs} itemToString={label}
      selectedItem={runs.find((r) => r.run_id === value) ?? null} onChange={({ selectedItem }) => selectedItem && onChange(selectedItem.run_id)} />
  )
}
