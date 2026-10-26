import { TrashCan } from '@carbon/icons-react'
import { Button } from '@carbon/react'
import { useEditorStore } from '../store'

const KIND = { distance: 'Jarak', 'room-area': 'Luas ruang', area: 'Luas bebas', height: 'Tinggi' }
const HINT = {
  distance: 'Klik titik A lalu B. Shift mengunci sumbu.', 'room-area': 'Klik lantai ruang.',
  area: 'Klik titik di lantai, klik dua kali untuk menutup.', height: 'Klik permukaan mana pun.',
}

/** Measurements are session-only: they never go into the spec (07 §5). */
export function MeasurePanel() {
  const { measurements, removeMeasurement, clearMeasurements, tool } = useEditorStore()
  return (
    <section className="editor-panel" aria-label="Ukuran">
      <h4 className="editor-panel__title">Ukuran</h4>
      {tool in HINT && <p className="helper">{HINT[tool as keyof typeof HINT]} Esc membatalkan.</p>}
      {!measurements.length && <p className="helper">Belum ada ukuran.</p>}
      <ul className="editor-measures">
        {measurements.map((m) => (
          <li key={m.id}>
            <span className="helper">{KIND[m.kind]}</span>
            <span className="mono">{m.label}</span>
            <Button kind="ghost" size="sm" hasIconOnly renderIcon={TrashCan} iconDescription="Hapus ukuran"
              tooltipPosition="left" onClick={() => removeMeasurement(m.id)} />
          </li>
        ))}
      </ul>
      {measurements.length > 0 && <Button kind="danger--ghost" size="sm" onClick={clearMeasurements}>Hapus semua</Button>}
    </section>
  )
}
