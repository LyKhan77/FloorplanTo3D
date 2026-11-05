import { Accordion, AccordionItem, Button, Checkbox, Dropdown, TextInput } from '@carbon/react'
import { useState, type ReactNode } from 'react'
import { api } from '../../api/client'
import type { Column, Opening, PlacedObject, Room, Spec, Stair, Wall } from '../../types/spec'
import { pointInPolygon } from '../lib/geom'
import { distance, formatM, formatM2 } from '../lib/measure'
import type { EditorOp } from '../ops/reducer'
import { useEditorStore } from '../store'
import type { Template } from '../../api/types'
import { templateOf } from '../lib/transform'
import { CorrectionPanel } from './CorrectionPanel'
import { MmInput } from './MmInput'
import { ObjectProps } from './ObjectProps'

/** RoomType enum (PRD/03 §6, core/spec/models.py). */
const ROOM_TYPES = [
  'data_hall', 'ups_room', 'battery_room', 'electrical_room', 'mdf', 'ahu_room', 'capacitor_room', 'meeting', 'office',
  'storage', 'pantry', 'toilet', 'corridor', 'lobby', 'stair', 'lift', 'prayer_room', 'outdoor',
  'server_room', 'network_room', 'control_room', 'security_room', 'fire_suppression_room', 'generator_room',
  'transformer_room', 'chiller_room', 'fuel_room', 'cable_vault', 'shaft', 'mechanical_room', 'workshop',
  'staging_room', 'loading_dock', 'reception', 'rest_room', 'locker_room', 'parking', 'other',
] as const

type Picked =
  | { kind: 'wall'; items: Wall[] } | { kind: 'room'; item: Room } | { kind: 'rooms'; items: Room[] } | { kind: 'door'; item: Opening }
  | { kind: 'walls+rooms'; walls: Wall[]; rooms: Room[] }
  | { kind: 'stair'; item: Stair } | { kind: 'column'; item: Column } | { kind: 'object'; item: PlacedObject }

function pick(view: Spec, ids: string[]): Picked | null {
  const rooms = (view.rooms ?? []).filter((r) => ids.includes(r.id))
  const rest = ids.filter((id) => !rooms.some((r) => r.id === id))
  if (rooms.length === 1 && rest.length) return pick(view, rest)  // a box that happens to hold one room
  const walls = rest.map((id) => view.walls?.find((w) => w.id === id))
  if (walls.length && walls.every(Boolean)) {
    return rooms.length ? { kind: 'walls+rooms', walls: walls as Wall[], rooms } : { kind: 'wall', items: walls as Wall[] }
  }
  if (rooms.length >= 2 && !rest.length) return { kind: 'rooms', items: ids.map((id) => rooms.find((r) => r.id === id)!) }
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

/** Asks the server for a merge plan over the unsaved ops, and applies it as one undo step. */
function useRoomPlan(route: 'merge-plan' | 'unmerge-plan') {
  const [busy, setBusy] = useState(false)
  const run = async (body: { room_ids: string[] } | { room_id: string }) => {
    const { projectId, baseVersion, ops, setNotice } = useEditorStore.getState()
    setBusy(true)
    try {
      const plan = await api.post<{ ops: EditorOp[] }>(`/api/projects/${projectId}/specs/${route}`, { base_version: baseVersion, ops, ...body })
      const s = useEditorStore.getState()
      // its wall ids were counted on the ops it was asked about
      if (s.ops !== ops) setNotice({ kind: 'warning', text: 'Denah berubah saat rencana dihitung; ulangi' })
      else if (s.applyMany(plan.ops)) s.select([])
    } catch (e) {
      setNotice({ kind: 'error', text: e instanceof Error ? e.message : String(e) })
    } finally {
      setBusy(false)
    }
  }
  return { busy, run }
}

function RoomProps({ room }: { room: Room }) {
  const { apply, applyMany } = useEditorStore()
  const [name, setName] = useState(room.name ?? '')
  const split = useRoomPlan('unmerge-plan')
  const merged = useEditorStore((s) => (s.view?.walls ?? []).some((w) => w.divides_room === false
    && pointInPolygon([(w.a[0] + w.b[0]) / 2, (w.a[1] + w.b[1]) / 2], room.polygon as [number, number][]) !== 'outside'))
  const rename = () => { if (name !== (room.name ?? '')) apply({ op: 'rename_room', id: room.id, name }) }
  return (
    <>
      <h4 className="editor-panel__title">Ruang {room.id}</h4>
      <TextInput id="room-name" labelText="Nama" size="sm" value={name} onChange={(e) => setName(e.target.value)} onBlur={rename}
        onKeyDown={(e) => { if (e.key === 'Enter') rename() }} />
      <Dropdown key={room.type ?? ''} id="room-type" titleText="Tipe" label="Pilih tipe" size="sm" items={[...ROOM_TYPES]}
        initialSelectedItem={room.type ?? null}
        onChange={({ selectedItem }) => { if (selectedItem && selectedItem !== room.type) apply({ op: 'set_room_type', id: room.id, type: selectedItem }) }} />
      <Info rows={[['Luas', room.area_m2 == null ? '—' : formatM2(room.area_m2)],
        ['Keliling', room.perimeter_m == null ? '—' : formatM(room.perimeter_m * 1000)],
        ['Pintu', (room.doors ?? []).join(', ') || '—']]} />
      {merged && <Button size="sm" kind="tertiary" disabled={split.busy} onClick={() => split.run({ room_id: room.id })}>Pisahkan ruangan</Button>}
      <MmInput id="room-height" label="Tinggi dinding ruang ini (mm)" value={null}
        onCommit={(v) => applyMany((room.bounding_walls ?? []).map((id) => ({ op: 'set_wall_height' as const, id, height: v })))} />
    </>
  )
}

function RoomsBulk({ items }: { items: Room[] }) {
  const applyMany = useEditorStore((s) => s.applyMany)
  const types = [...new Set(items.map((r) => r.type))]
  const merge = useRoomPlan('merge-plan')
  return (
    <>
      <h4 className="editor-panel__title">{items.length} ruang terseleksi</h4>
      <Dropdown key={types.join()} id="rooms-type" titleText="Tipe semua ruang" label={types.length === 1 ? (types[0] ?? 'Pilih tipe') : 'Campuran'}
        size="sm" items={[...ROOM_TYPES]} selectedItem={null}
        onChange={({ selectedItem: t }) => {
          if (t) applyMany(items.filter((r) => r.type !== t).map((r) => ({ op: 'set_room_type' as const, id: r.id, type: t })))
        }} />
      <Button size="sm" kind="tertiary" disabled={merge.busy} onClick={() => merge.run({ room_ids: items.map((r) => r.id) })}>Gabung ruangan</Button>
    </>
  )
}

function Body({ picked, view, templates }: { picked: Picked; view: Spec; templates: Template[] }) {
  switch (picked.kind) {
    case 'wall': return <WallProps items={picked.items} view={view} />
    case 'rooms': return <RoomsBulk items={picked.items} />
    case 'walls+rooms': return <><WallProps items={picked.walls} view={view} /><RoomsBulk items={picked.rooms} /></>
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
      const setFlight = (i: number, change: Partial<Stair['flights'][number]>) => useEditorStore.getState().apply(
        { op: 'set_stair', id: s.id, flights: s.flights.map((f, k) => (k === i ? { ...f, ...change } : f)) as Stair['flights'] })
      return (
        <>
          <h4 className="editor-panel__title">Tangga {s.id}</h4>
          {s.flights.map((f, i) => (
            <div key={i}>
              <MmInput id={`flight-width-${i}`} label={`Lebar flight ${i + 1} (mm)`} value={f.width} min={500} max={6000}
                onCommit={(width) => setFlight(i, { width })} />
              <MmInput id={`flight-risers-${i}`} label={`Anak tangga flight ${i + 1}`} value={f.risers} min={2} max={60}
                unit="anak tangga" onCommit={(risers) => setFlight(i, { risers })} />
            </div>
          ))}
          <Info rows={[['Flight', s.flights.length],
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
      return <ObjectProps key={`${o.id}:${o.label}`} o={o} t={templateOf(o, templates)} />
    }
  }
}

export function PropertiesPanel({ templates = [], rooms }: { templates?: Template[]; rooms?: Room[] | null }) {
  const stored = useEditorStore((s) => s.view)
  const selection = useEditorStore((s) => s.selection)
  const tool = useEditorStore((s) => s.tool)
  if (!stored) return null
  // the client never rebuilds rooms: a known room reads from the dry run; one only the dry run knows stays unpicked,
  // because the reducer could not rename it
  const dry = new Map((rooms ?? []).map((r) => [r.id, r]))
  const view = { ...stored, rooms: stored.rooms?.map((r) => dry.get(r.id) ?? r) }
  const picked = selection.length ? pick(view, selection) : null
  return (
    <section className="editor-panel" aria-label="Properties">
      {!selection.length && <DefaultHeight view={view} />}
      {selection.length > 0 && !picked && <p className="helper">{selection.length} elemen terseleksi</p>}
      {picked && <Body picked={picked} view={view} templates={templates} />}
      {(!selection.length || (picked && ['wall', 'walls+rooms', 'door', 'stair'].includes(picked.kind))) && (
        <Accordion size="sm" className="editor-correction">
          <AccordionItem title="Koreksi" open={tool === 'add-wall' || undefined}><CorrectionPanel /></AccordionItem>
        </Accordion>
      )}
    </section>
  )
}
