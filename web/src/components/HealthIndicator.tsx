import { Link } from 'react-router-dom'
import { useHealth } from '../api/hooks'

function Dot({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <span className="health-item" title={`${label}: ${value}`}>
      <span className="health-dot" style={{ background: color }} aria-hidden="true" />
      <span className="health-label">{label}</span>
      <span className="cds--visually-hidden">: {value}</span>
    </span>
  )
}

export function HealthIndicator() {
  const { data } = useHealth()
  const strata = !data ? ['#6f6f6f', 'memuat'] : !data.strata.ok ? ['#fa4d56', 'mati'] : data.strata.status === 'processing' ? ['#4589ff', 'memproses'] : ['#42be65', 'siap']
  const blender = !data ? ['#6f6f6f', 'memuat'] : !data.blender.ok ? ['#fa4d56', 'tidak ada'] : data.blender.busy ? ['#4589ff', 'sibuk'] : ['#42be65', 'siap']
  const waiting = data?.queue.waiting ?? 0
  return (
    <Link to="/system" className="health-indicator" aria-label="Status sistem">
      <Dot color={strata[0]} label="Strata" value={strata[1]} />
      <Dot color={blender[0]} label="Blender" value={blender[1]} />
      <span className="health-item mono" title="Run dalam antrean">Antrean {waiting}</span>
    </Link>
  )
}
