import { CheckmarkFilled, CircleDash, Edit, ErrorFilled, InProgress, SubtractAlt, WarningAltFilled, WarningFilled } from '@carbon/icons-react'
import type { CarbonIconType } from '@carbon/icons-react'
import type { StageStatus } from '../api/types'

// PRD/08 §5: status is never conveyed by colour alone — icon + text + colour.
const STATUS: Record<string, { icon: CarbonIconType; color: string; text: string }> = {
  pending: { icon: CircleDash, color: '#6f6f6f', text: 'Menunggu' },
  queued: { icon: CircleDash, color: '#6f6f6f', text: 'Menunggu' },
  new: { icon: CircleDash, color: '#6f6f6f', text: 'Baru' },
  running: { icon: InProgress, color: '#4589ff', text: 'Berjalan' },
  succeeded: { icon: CheckmarkFilled, color: '#42be65', text: 'Selesai' },
  warning: { icon: WarningAltFilled, color: '#f1c21b', text: 'Selesai dengan peringatan' },
  needs_attention: { icon: WarningFilled, color: '#f1c21b', text: 'Perlu perhatian' },
  needs_review: { icon: Edit, color: '#f1c21b', text: 'Perlu review' },
  failed: { icon: ErrorFilled, color: '#fa4d56', text: 'Gagal' },
  skipped: { icon: SubtractAlt, color: '#8d8d8d', text: 'Dilewati' },
}

export function StatusTag({ status, warning = false }: { status: StageStatus | string; warning?: boolean }) {
  const s = warning && status === 'succeeded' ? STATUS.warning : STATUS[status] ?? STATUS.pending
  const Icon = s.icon
  return (
    <span className={`status-tag${status === 'running' ? ' status-tag--running' : ''}`}>
      <Icon size={16} style={{ fill: s.color, flexShrink: 0 }} aria-hidden="true" />
      <span>{s.text}</span>
    </span>
  )
}
