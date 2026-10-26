import { ContentSwitcher, Switch, TextInput, Toggle } from '@carbon/react'
import { useState } from 'react'
import type { Template } from '../../api/types'
import type { PlacedObject } from '../../types/spec'
import { formatM } from '../lib/measure'
import { clampDims } from '../lib/resize'
import { moveOps } from '../lib/transform'
import { useEditorStore, type Gizmo } from '../store'
import { MmInput } from './MmInput'

const FAR = 10_000_000
const GIZMOS: [Gizmo, string][] = [['translate', 'Pindah'], ['rotate', 'Putar'], ['scale', 'Ubah ukuran']]
const AXES = [['w', 'W'], ['d', 'D'], ['h', 'H']] as const

/** Numeric edits of one object; edits of an unsaved object fold into its add_object (pushOp). */
export function ObjectProps({ o, t }: { o: PlacedObject; t: Template | undefined }) {
  const { apply, applyMany, setNotice, gizmo, setGizmo } = useEditorStore()
  const [label, setLabel] = useState(o.label ?? '')
  const update = (fields: Partial<PlacedObject>) => apply({ op: 'update_object', id: o.id, ...fields } as never)
  const moveTo = (x: number, y: number) => {
    const view = useEditorStore.getState().view!
    const r = moveOps([o], [x - o.position[0], y - o.position[1]], view, false, t ? [t] : [])
    if ('error' in r) setNotice({ kind: 'error', text: r.error })
    else applyMany(r)
  }
  const setDim = (i: number, v: number) => {
    const dims = [...o.dims] as [number, number, number]
    dims[i] = v
    update({ dims: t ? clampDims(dims, t) : dims })
  }
  const commitLabel = () => { if (label !== (o.label ?? '')) update({ label: label.trim() ? label : null }) }
  const fixed = t?.scale_mode === 'fixed'
  const locked = !!o.locked // only "Terkunci" stays editable
  return (
    <>
      <h4 className="editor-panel__title">Objek {o.id}</h4>
      <p className="helper">{t?.name ?? o.template_id} · v{o.template_version}{o.room_id ? ` · ${o.room_id}` : ''}</p>
      <ContentSwitcher size="sm" selectedIndex={GIZMOS.findIndex(([g]) => g === gizmo)}
        onChange={({ index }) => setGizmo(GIZMOS[index ?? 0][0])}>
        {GIZMOS.map(([g, text]) => <Switch key={g} name={g} text={text} />)}
      </ContentSwitcher>
      <div className="editor-grid3">
        <MmInput id="obj-x" label="X (mm)" value={o.position[0]} min={-FAR} max={FAR} disabled={locked} onCommit={(v) => moveTo(v, o.position[1])} />
        <MmInput id="obj-y" label="Y (mm)" value={o.position[1]} min={-FAR} max={FAR} disabled={locked} onCommit={(v) => moveTo(o.position[0], v)} />
        <MmInput id="obj-z" label="Z (mm)" value={o.position[2]} min={-FAR} max={FAR} disabled={locked}
          onCommit={(v) => update({ position: [o.position[0], o.position[1], v] })} />
      </div>
      <MmInput id="obj-rot" label="Rotasi (°)" unit="°" value={o.rotation ?? 0} min={-360} max={360} disabled={locked}
        onCommit={(v) => update({ rotation: ((v % 360) + 360) % 360 })} />
      <div className="editor-grid3">
        {AXES.map(([k, name], i) => (
          <MmInput key={k} id={`obj-${k}`} label={`${name} (mm)`} value={o.dims[i]} min={1} max={FAR}
            disabled={locked || fixed || (t ? !t.resizable?.[k] : false)} onCommit={(v) => setDim(i, v)} />
        ))}
      </div>
      <TextInput id="obj-label" labelText="Label" size="sm" value={label} disabled={locked} onChange={(e) => setLabel(e.target.value)}
        onBlur={commitLabel} onKeyDown={(e) => { if (e.key === 'Enter') commitLabel() }} />
      <Toggle id="obj-locked" size="sm" labelText="Terkunci" labelA="tidak" labelB="ya" toggled={!!o.locked}
        onToggle={(on) => update({ locked: on })} />
      {t?.metadata && Object.keys(t.metadata).length > 0 && (
        <dl className="editor-info">
          {Object.entries(t.metadata).map(([k, v]) => <div key={k}><dt>{k}</dt><dd className="mono">{String(v)}</dd></div>)}
        </dl>
      )}
      <p className="helper mono">{formatM(o.dims[0])} × {formatM(o.dims[1])} × {formatM(o.dims[2])}</p>
    </>
  )
}
