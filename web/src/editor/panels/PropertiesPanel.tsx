import { Button, Checkbox, Dropdown, TextInput } from '@carbon/react'
import { useState, type ReactNode } from 'react'
import type { Column, Opening, PlacedObject, Room, Spec, Stair, Wall } from '../../types/spec'
import { distance, formatM, formatM2 } from '../lib/measure'
import { useEditorStore } from '../store'
import { MmInput } from './MmInput'

/** RoomType enum (PRD/03 §6, core/spec/models.py). */
const ROOM_TYPES = [
  'data_hall', 'ups_room', 'battery_room', 'electrical_room', 'mdf', 'ahu_room', 'capacitor_room', 'meeting', 'office',
  'storage', 'pantry', 'toilet', 'corridor', 'lobby', 'stair', 'lift', 'prayer_room', 'outdoor', 'other',
] as const

type Picked =
  | { kind: 'wall'; items: Wall[] } | { kind: 'room'; item: Room } | { kind: 'door'; item: Opening }
  | { kind: 'stair'; item: Stair } | { kind: 'column'; item: Column } | { kind: 'object'; item: PlacedObject }

function pick(view: Spec, ids: string[]): Picked | null {
  const walls = ids.map((id) => view.walls?.find((w) => w.id === id))
  if (walls.length && walls.every(Boolean)) return { kind: 'wall', items: walls as Wall[] }
  if (ids.length !== 1) return null
  const id = ids[0]
  const find = <T extends { id: string }>(xs: T[] | undefined) => xs?.find((x) => x.id === id)
  const room = find(view.rooms), door = find(view.openings), stair = find(view.stairs), col = find(view.columns),
    obj = find(view.objects)
  if (room) return { kind: 'room', item: room }
  if (door) return { kind: 'door', item: door }
  if (stair) return { kind: 'stair', item: stair }
  if (col) return { kind: 'column', item: col }
  if (obj) return { kind: 'object', item: obj }
  return null
}

function Info({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="editor-info">
      {rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd className="mono">{v ?? '—'}</dd></div>)}
    </dl>
  )
}

const mm = (v: number | null | undefined) => (v == null ? '—' : formatM(v))

function DefaultHeight({ view }: { view: Spec }) {
  const applyMany = useEditorStore((s) => s.applyMany)
  const [all, setAll] = useState(false)
  return (
    <>
      <h4 className="editor-panel__title">Bangunan</h4>
      <MmInput id="default-height" label="Tinggi dinding default (mm)" value={view.meta.defaults?.wall_height}
        onCommit={(v) => applyMany([{ op: 'set_default', key: 'wall_height', value: v },
          ...(all ? [{ op: 'set_wall_height' as const, id: '*', height: null }] : [])])} />
      <Checkbox id="default-height-all" labelText="Terapkan juga ke dinding yang tingginya diatur khusus" checked={all}
        onChange={(_, { checked }) => setAll(checked)} />
    </>
  )
}

function WallProps({ items, view }: { items: Wall[]; view: Spec }) {
  const applyMany = useEditorStore((s) => s.applyMany)
  const def = view.meta.defaults?.wall_height ?? 3000
  const heights = [...new Set(items.map((w) => w.height ?? def))]
  const setAll = (height: number | null) => applyMany(items.map((w) => ({ op: 'set_wall_height' as const, id: w.id, height })))
  const w = items[0]
  return (
    <>
      <h4 className="editor-panel__title">{items.length === 1 ? `Dinding ${w.id}` : `${items.length} dinding`}</h4>
      {items.length === 1 && (
        <Info rows={[['Panjang', formatM(distance(w.a, w.b).d)], ['Tebal', `${w.thickness} mm`], ['Kind', w.kind],
          ['Tinggi', w.height == null ? `default (${formatM(def)})` : formatM(w.height)]]} />
      )}
      <MmInput id="wall-height" label="Tinggi (mm)" value={heights.length === 1 ? heights[0] : null} onCommit={setAll} />
      <Button kind="ghost" size="sm" onClick={() => setAll(null)}>Ikut default</Button>
    </>
  )
}

function RoomProps({ room }: { room: Room }) {
  const { apply, applyMany } = useEditorStore()
  const [name, setName] = useState(room.name ?? '')
  const rename = () => { if (name !== (room.name ?? '')) apply({ op: 'rename_room', id: room.id, name }) }
  return (
    <>
      <h4 className="editor-panel__title">Ruang {room.id}</h4>
      <TextInput id="room-name" labelText="Nama" size="sm" value={name} onChange={(e) => setName(e.target.value)} onBlur={rename}
        onKeyDown={(e) => { if (e.key === 'Enter') rename() }} />
      <Dropdown id="room-type" titleText="Tipe" label="Pilih tipe" size="sm" items={[...ROOM_TYPES]}
        selectedItem={room.type ?? null}
        onChange={({ selectedItem }) => { if (selectedItem) apply({ op: 'set_room_type', id: room.id, type: selectedItem }) }} />
      <Info rows={[['Luas', room.area_m2 == null ? '—' : formatM2(room.area_m2)],
        ['Keliling', room.perimeter_m == null ? '—' : formatM(room.perimeter_m * 1000)],
        ['Pintu', (room.doors ?? []).join(', ') || '—']]} />
      <MmInput id="room-height" label="Tinggi dinding ruang ini (mm)" value={null}
        onCommit={(v) => applyMany((room.bounding_walls ?? []).map((id) => ({ op: 'set_wall_height' as const, id, height: v })))} />
    </>
  )
}

function Body({ picked, view }: { picked: Picked; view: Spec }) {
  switch (picked.kind) {
    case 'wall': return <WallProps items={picked.items} view={view} />
    case 'room': return <RoomProps key={`${picked.item.id}:${picked.item.name}`} room={picked.item} />
    case 'door': {
      const d = picked.item
      return (
        <>
          <h4 className="editor-panel__title">{d.category === 'door' ? 'Pintu' : 'Jendela'} {d.id}</h4>
          <Info rows={[['Tipe', d.door_type], ['Lebar', mm(d.width)], ['Tinggi', mm(d.height)], ['Engsel', d.hinge],
            ['Arah', d.swing], ['Offset', mm(d.offset)], ['Dinding', d.wall_id]]} />
        </>
      )
    }
    case 'stair': {
      const s = picked.item
      return (
        <>
          <h4 className="editor-panel__title">Tangga {s.id}</h4>
          <Info rows={[['Flight', s.flights.length], ['Tanjakan', s.flights.map((f) => f.risers).join(' + ')],
            ['Lebar', s.flights.map((f) => formatM(f.width)).join(', ')],
            ['Arah naik', s.flights.map((f) => `(${f.start.join(', ')}) → (${f.end.join(', ')})`).join('; ')],
            ['top_z', s.top_z == null ? 'default' : formatM(s.top_z)]]} />
        </>
      )
    }
    case 'column': {
      const c = picked.item
      return (
        <>
          <h4 className="editor-panel__title">Kolom {c.id}</h4>
          <Info rows={[['Ukuran', `${c.size.join(' × ')} mm`], ['Bentuk', c.shape], ['Kind', c.kind]]} />
        </>
      )
    }
    case 'object': {
      const o = picked.item
      return (
        <>
          <h4 className="editor-panel__title">Objek {o.id}</h4>
          <Info rows={[['Template', `${o.template_id}@${o.template_version}`], ['Label', o.label],
            ['Posisi', `${o.position.map((v) => formatM(v)).join(', ')}`], ['Rotasi', `${o.rotation ?? 0}°`],
            ['Dimensi', `${o.dims.join(' × ')} mm`], ['Ruang', o.room_id], ['Terkunci', o.locked ? 'ya' : 'tidak']]} />
        </>
      )
    }
  }
}

export function PropertiesPanel() {
  const view = useEditorStore((s) => s.view)
  const selection = useEditorStore((s) => s.selection)
  if (!view) return null
  const picked = selection.length ? pick(view, selection) : null
  return (
    <section className="editor-panel" aria-label="Properties">
      {!selection.length && <DefaultHeight view={view} />}
      {selection.length > 0 && !picked && <p className="helper">{selection.length} elemen terseleksi</p>}
      {picked && <Body picked={picked} view={view} />}
    </section>
  )
}
