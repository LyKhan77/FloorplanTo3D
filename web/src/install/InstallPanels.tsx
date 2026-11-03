import { ErrorFilled, InformationFilled, WarningAltFilled } from '@carbon/icons-react'
import { Button, Dropdown, NumberInput, TextInput } from '@carbon/react'
import { DeleteWithReason } from '../editor/panels/DeleteWithReason'
import type { CableTray, PlacedObject } from '../types/installation'
import type { InstallIssue, InstallValidation } from './api'
import { SIDE_HEIGHTS, TRAY_WIDTHS, type InstallOp } from './reducer'
import { useInstallStore } from './store'
import { MOVE_REASON, TURN_REASON } from './deviceOps'

const ICON = { error: ErrorFilled, warning: WarningAltFilled, info: InformationFilled }
const MOUNT = ['default', 'overhead', 'underfloor'] as const
const m = (mm: number) => (mm / 1000).toFixed(1)
const apply = (op: InstallOp) => useInstallStore.getState().apply(op)

function TrayForm({ t }: { t: CableTray }) {
  const set = (fields: Partial<CableTray>) => apply({ op: 'set_tray', id: t.id, ...fields } as InstallOp)
  return (
    <>
      <h5 className="editor-panel__sub">Tray {t.id}</h5>
      <Dropdown id="it-class" titleText="Kelas" label="Kelas" size="sm" items={['data', 'power'] as const} selectedItem={t.tray_class}
        onChange={({ selectedItem }) => selectedItem && selectedItem !== t.tray_class && set({ tray_class: selectedItem })} />
      <div className="editor-grid2">
        <Dropdown id="it-width" titleText="Lebar (mm)" label="Lebar" size="sm" items={TRAY_WIDTHS} itemToString={(v) => String(v ?? '')}
          selectedItem={t.width ?? null} onChange={({ selectedItem }) => selectedItem && set({ width: selectedItem })} />
        <Dropdown id="it-side" titleText="Tinggi sisi (mm)" label="Tinggi sisi" size="sm" items={SIDE_HEIGHTS} itemToString={(v) => String(v ?? '')}
          selectedItem={t.side_height ?? 100} onChange={({ selectedItem }) => selectedItem && set({ side_height: selectedItem })} />
      </div>
      <Dropdown id="it-mount" titleText="Pemasangan" label="Pemasangan" size="sm" items={[...MOUNT]} selectedItem={t.mounting ?? 'default'}
        itemToString={(v) => (v === 'default' ? 'Default instalasi' : v === 'overhead' ? 'Overhead' : v === 'underfloor' ? 'Underfloor' : '')}
        onChange={({ selectedItem }) => set({ mounting: (selectedItem === 'default' ? null : selectedItem ?? null) as CableTray['mounting'] })} />
      <NumberInput id="it-elev" label="Elevasi sisi bawah (mm, kosong = default)" size="sm" allowEmpty hideSteppers
        value={t.elevation ?? ''} onBlur={(e) => {
          const v = (e.target as HTMLInputElement).value.trim()
          set({ elevation: v === '' ? null : Math.round(Number(v)) })
        }} />
      <DeleteWithReason id="it-del" label="Hapus tray" onDelete={(reason) => apply({ op: 'delete_tray', id: t.id, reason })} />
    </>
  )
}

function RackForm({ o }: { o: PlacedObject }) {
  // a device: where it stands (Z: wall-mounted panels and cameras hang), how it turns, how big it is
  const field = (id: string, label: string, value: number, set: (v: number) => void) => (
    <TextInput id={id} key={`${id}-${value}`} labelText={label} size="sm" type="number" defaultValue={String(Math.round(value))}
      onBlur={(e) => { const v = Number(e.target.value); if (e.target.value !== '' && Number.isFinite(v) && v !== Math.round(value)) set(v) }} />
  )
  const [x, y, z] = o.position, [w, d, h] = o.dims
  return (
    <>
      <h5 className="editor-panel__sub">Perangkat {o.id}</h5>
      <p className="helper mono">{o.template_id} · {o.dims.join(' × ')} mm</p>
      <TextInput id="ir-label" labelText="Label" size="sm" defaultValue={o.label ?? ''}
        onBlur={(e) => { if ((e.target.value || null) !== (o.label ?? null)) apply({ op: 'update_object', id: o.id, label: e.target.value || null }) }} />
      <div className="install-device-grid">
        {field('ir-x', 'X (mm)', x, (v) => apply({ op: 'update_object', id: o.id, position: [v, y, z], reason: MOVE_REASON }))}
        {field('ir-y', 'Y (mm)', y, (v) => apply({ op: 'update_object', id: o.id, position: [x, v, z], reason: MOVE_REASON }))}
        {field('ir-z', 'Z (mm)', z, (v) => apply({ op: 'update_object', id: o.id, position: [x, y, v], reason: MOVE_REASON }))}
        {field('ir-rot', 'Rotasi (°)', o.rotation ?? 0, (v) => apply({ op: 'update_object', id: o.id, rotation: ((v % 360) + 360) % 360, reason: TURN_REASON }))}
        {field('ir-w', 'Lebar (mm)', w, (v) => apply({ op: 'update_object', id: o.id, dims: [v, d, h] }))}
        {field('ir-d', 'Dalam (mm)', d, (v) => apply({ op: 'update_object', id: o.id, dims: [w, v, h] }))}
        {field('ir-h', 'Tinggi (mm)', h, (v) => apply({ op: 'update_object', id: o.id, dims: [w, d, v] }))}
      </div>
      <DeleteWithReason id="ir-del" label="Hapus perangkat" onDelete={(reason) => apply({ op: 'delete_object', id: o.id, reason })} />
    </>
  )
}

function MetaForm() {
  const meta = useInstallStore((s) => s.view?.meta)
  if (!meta) return null
  const height = (field: 'ceiling_height' | 'raised_floor_height', raw: string) => {
    const v = raw.trim() === '' ? null : Math.round(Number(raw))
    if (Number.isNaN(v as number) || v === (meta[field] ?? null)) return
    apply({ op: 'set_installation_meta', [field]: v } as InstallOp)
  }
  return (
    <>
      <h5 className="editor-panel__sub">Instalasi</h5>
      <NumberInput id="im-ceiling" label="Tinggi plafon (mm, kosong = tinggi dinding)" size="sm" allowEmpty hideSteppers
        defaultValue={meta.ceiling_height ?? ''} onBlur={(e) => height('ceiling_height', (e.target as HTMLInputElement).value)} />
      <NumberInput id="im-raised" label="Tinggi raised floor (mm, kosong = tidak ada)" size="sm" allowEmpty hideSteppers
        defaultValue={meta.raised_floor_height ?? ''} onBlur={(e) => height('raised_floor_height', (e.target as HTMLInputElement).value)} />
      <Dropdown id="im-mount" titleText="Pemasangan default" label="Pemasangan" size="sm" items={['overhead', 'underfloor'] as const}
        selectedItem={meta.default_mounting ?? 'overhead'} itemToString={(v) => (v === 'underfloor' ? 'Underfloor' : 'Overhead')}
        onChange={({ selectedItem }) => selectedItem && selectedItem !== meta.default_mounting && apply({ op: 'set_installation_meta', default_mounting: selectedItem })} />
    </>
  )
}

/** Right panel in mode Instalasi: the selected tray or rack, the issues, and the tray lengths (M12a). */
export function InstallPanels({ validation, saveIssues }: { validation: InstallValidation; saveIssues: InstallIssue[] }) {
  const view = useInstallStore((s) => s.view)
  const selection = useInstallStore((s) => s.selection)
  const id = selection.length === 1 ? selection[0] : null
  const tray = view?.cable_trays?.find((t) => t.id === id), rack = view?.objects?.find((o) => o.id === id)
  const issues = [...saveIssues, ...validation.issues.filter((i) => !saveIssues.some((s) => s.code === i.code && s.element_ids.join() === i.element_ids.join()))]
  const L = validation.lengths
  return (
    <>
      <section className="editor-panel" aria-label="Properti instalasi">
        <h4 className="editor-panel__title">Properti</h4>
        {tray ? <TrayForm key={tray.id} t={tray} /> : rack ? <RackForm key={rack.id} o={rack} />
          : <><MetaForm /><p className="helper">Pilih tray atau rack. Tray: T, klik jalur, Enter. Rack: K, klik di dalam kotak.</p></>}
      </section>
      <section className="editor-panel" aria-label="Masalah instalasi">
        <h4 className="editor-panel__title">Masalah ({issues.length})</h4>
        {!issues.length && <p className="helper">Tidak ada masalah.</p>}
        <ul className="editor-issues">
          {issues.map((i, n) => {
            const Icon = ICON[i.severity]
            return (
              <li key={`${i.code}|${i.element_ids.join()}#${n}`} className={`editor-issue editor-issue--${i.severity}`}>
                <Icon aria-label={i.severity} />
                <div>
                  <span className="mono">{i.code}</span>
                  <p>{i.message}</p>
                  <span className="editor-issue__ids">
                    {i.element_ids.map((e) => <Button key={e} kind="ghost" size="sm" onClick={() => useInstallStore.getState().select([e])}>{e}</Button>)}
                  </span>
                </div>
              </li>
            )
          })}
        </ul>
      </section>
      <section className="editor-panel" aria-label="Panjang tray">
        <h4 className="editor-panel__title">Panjang tray (m)</h4>
        <table className="cds--data-table cds--data-table--compact install-lengths">
          <thead><tr><th>Kelas</th><th>Jalur</th><th>Drop</th><th>Total</th></tr></thead>
          <tbody>
            {(['data', 'power'] as const).map((c) => (
              <tr key={c} aria-label={c === 'data' ? 'Data' : 'Power'}>
                <td>{c === 'data' ? 'Data' : 'Power'}</td>
                <td className="mono">{L ? m(L[c].horizontal) : '—'}</td>
                <td className="mono">{L ? m(L[c].drops) : '—'}</td>
                <td className="mono">{L ? m(L[c].total) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  )
}
