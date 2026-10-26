import { Button, Checkbox, Slider } from '@carbon/react'
import { useEditorStore, type Layer } from '../store'

const LABELS: [Layer, string][] = [
  ['walls', 'Dinding'], ['columns', 'Kolom'], ['doors', 'Pintu'], ['objects', 'Objek'], ['labels', 'Label ruang'],
  ['grid', 'Grid 600'], ['axes', 'Sumbu grid'],
]
const CUT_DEFAULT = 3000

export function LayersPanel() {
  const { layers, toggleLayer, cutaway, setCutaway, view, select, selection, setFocus, mode } = useEditorStore()
  return (
    <section className="editor-panel" aria-label="Layers">
      <h4 className="editor-panel__title">Layer</h4>
      {LABELS.map(([k, label]) => (
        <Checkbox key={k} id={`layer-${k}`} labelText={label} checked={layers[k]} onChange={() => toggleLayer(k)} />
      ))}
      <Checkbox id="layer-cutaway" labelText="Cutaway" checked={cutaway !== null}
        onChange={(_, { checked }) => setCutaway(checked ? CUT_DEFAULT : null)} />
      {cutaway !== null && (
        <Slider id="cutaway" labelText="Tinggi potong (mm)" min={1000} max={12000} step={100} value={cutaway}
          onChange={({ value }) => setCutaway(value)} />
      )}
      <h4 className="editor-panel__title">Rooms</h4>
      <ul className="editor-rooms">
        {(view?.rooms ?? []).map((r) => (
          <li key={r.id}>
            <Button kind={selection.includes(r.id) ? 'secondary' : 'ghost'} size="sm" onClick={() => { select([r.id]); if (r.label_pos) setFocus([r.label_pos[0], r.label_pos[1]]) }}
              title={mode === 'walk' ? 'Teleport ke ruang ini' : 'Fokus kamera ke ruang ini'}>
              {r.name ? `${r.name} · ${r.id}` : r.id}
            </Button>
          </li>
        ))}
      </ul>
    </section>
  )
}
