import { Button, Dropdown } from '@carbon/react'
import { useState } from 'react'
import type { SetStair } from '../../types/ops'
import type { Opening, Stair, Wall } from '../../types/spec'
import { distance } from '../lib/measure'
import type { EditorOp } from '../ops/reducer'
import { useEditorStore } from '../store'
import { BulkWalls } from './BulkWalls'
import { DeleteWithReason } from './DeleteWithReason'
import { MmInput } from './MmInput'

const FAR = 10_000_000
const KINDS = ['exterior', 'interior', 'partition', 'glass', 'low'] as const
const DOOR_TYPES = ['single_swing', 'double_swing', 'sliding', 'opening', 'rolling'] as const
const HINGES = ['start', 'end', 'both'] as const
const SWINGS = ['left', 'right'] as const
type Pt = [number, number]

const apply = (op: EditorOp) => useEditorStore.getState().apply(op)

function WallForm({ w }: { w: Wall }) {
  const [cat, setCat] = useState<'door' | 'window'>('door')
  const [offset, setOffset] = useState<number | null>(null)
  const [width, setWidth] = useState<number | null>(null)
  const len = Math.round(distance(w.a, w.b).d)
  const end = (k: 'a' | 'b', i: 0 | 1, v: number) => {
    const p = [...w[k]] as Pt
    p[i] = v
    apply({ op: 'move_wall', id: w.id, [k]: p })
  }
  return (
    <>
      <div className="editor-grid2">
        <MmInput id="cw-ax" label="a.x (mm)" value={w.a[0]} min={-FAR} max={FAR} onCommit={(v) => end('a', 0, v)} />
        <MmInput id="cw-ay" label="a.y (mm)" value={w.a[1]} min={-FAR} max={FAR} onCommit={(v) => end('a', 1, v)} />
        <MmInput id="cw-bx" label="b.x (mm)" value={w.b[0]} min={-FAR} max={FAR} onCommit={(v) => end('b', 0, v)} />
        <MmInput id="cw-by" label="b.y (mm)" value={w.b[1]} min={-FAR} max={FAR} onCommit={(v) => end('b', 1, v)} />
      </div>
      <MmInput id="cw-t" label="Tebal (mm)" value={w.thickness} min={10} max={2000} onCommit={(v) => apply({ op: 'move_wall', id: w.id, thickness: v })} />
      <Dropdown key={w.kind} id="cw-kind" titleText="Kind" label="Kind" size="sm" items={[...KINDS]} initialSelectedItem={w.kind}
        onChange={({ selectedItem }) => { if (selectedItem && selectedItem !== w.kind) apply({ op: 'move_wall', id: w.id, kind: selectedItem }) }} />
      <MmInput id="cw-split" label="Pisah di offset (mm dari a)" value={null} min={1} max={Math.max(1, len - 1)}
        onCommit={(v) => apply({ op: 'split_wall', id: w.id, at_offset: v })} />
      <h5 className="editor-panel__sub">Tambah pintu/jendela</h5>
      <Dropdown id="cw-cat" titleText="Kategori" label="Kategori" size="sm" items={['door', 'window'] as const} selectedItem={cat}
        onChange={({ selectedItem }) => setCat(selectedItem ?? 'door')} />
      <div className="editor-grid2">
        <MmInput id="cw-ooff" label="Offset (mm)" value={offset} min={0} max={len} onCommit={setOffset} />
        <MmInput id="cw-ow" label="Lebar bukaan (mm)" value={width} min={100} max={len} onCommit={setWidth} />
      </div>
      <Button size="sm" kind="tertiary" disabled={offset === null || width === null}
        onClick={() => apply({ op: 'add_opening', wall_id: w.id, category: cat, offset: offset!, width: width!,
          ...(cat === 'door' ? { door_type: 'single_swing' as const, hinge: 'start' as const, swing: 'left' as const } : {}) })}>
        Tambah bukaan
      </Button>
      <DeleteWithReason id="cw-del" label="Hapus dinding" onDelete={(reason) => apply({ op: 'delete_wall', id: w.id, reason })} />
    </>
  )
}

function DoorForm({ d }: { d: Opening }) {
  if (d.category !== 'door') {
    return <DeleteWithReason id="cd-del" label="Hapus jendela" onDelete={(reason) => apply({ op: 'delete_opening', id: d.id, reason })} />
  }
  const set = (fields: Record<string, unknown>) => apply({ op: 'set_door', id: d.id, ...fields } as EditorOp)
  return (
    <>
      <Dropdown key={d.door_type ?? ''} id="cd-type" titleText="Tipe" label="Tipe" size="sm" items={[...DOOR_TYPES]} initialSelectedItem={d.door_type ?? null}
        onChange={({ selectedItem }) => { if (selectedItem && selectedItem !== d.door_type) set({ door_type: selectedItem }) }} />
      <div className="editor-grid2">
        <MmInput id="cd-w" label="Lebar (mm)" value={d.width} min={100} max={10000} onCommit={(v) => set({ width: v })} />
        <MmInput id="cd-h" label="Tinggi (mm)" value={d.height} min={100} max={12000} onCommit={(v) => set({ height: v })} />
        <MmInput id="cd-off" label="Offset (mm)" value={d.offset} min={0} max={FAR} onCommit={(v) => set({ offset: v })} />
      </div>
      <Dropdown key={d.hinge ?? ''} id="cd-hinge" titleText="Engsel" label="Engsel" size="sm" items={[...HINGES]} initialSelectedItem={d.hinge ?? null}
        onChange={({ selectedItem }) => { if (selectedItem && selectedItem !== d.hinge) set({ hinge: selectedItem }) }} />
      <Dropdown key={d.swing ?? ''} id="cd-swing" titleText="Arah buka" label="Arah buka" size="sm" items={[...SWINGS]} initialSelectedItem={d.swing ?? null}
        onChange={({ selectedItem }) => { if (selectedItem && selectedItem !== d.swing) set({ swing: selectedItem }) }} />
      <DeleteWithReason id="cd-del" label="Hapus pintu" onDelete={(reason) => apply({ op: 'delete_opening', id: d.id, reason })} />
    </>
  )
}

function StairForm({ s }: { s: Stair }) {
  const flights = (patch: (f: Stair['flights'][number], i: number) => Partial<Stair['flights'][number]>) =>
    apply({ op: 'set_stair', id: s.id, flights: s.flights.map((f, i) => ({ ...f, ...patch(f, i) })) as SetStair['flights'] })
  return (
    <>
      {s.flights.map((f, i) => (
        <MmInput key={i} id={`cs-r${i}`} label={`Tanjakan flight ${i + 1}`} unit="anak tangga" value={f.risers} min={1} max={60}
          onCommit={(v) => flights((_, j) => (j === i ? { risers: v } : {}))} />
      ))}
      <MmInput id="cs-w" label="Lebar semua flight (mm)" value={s.flights[0]?.width} min={300} max={10000} onCommit={(v) => flights(() => ({ width: v }))} />
      <MmInput id="cs-top" label="top_z (mm)" value={s.top_z} min={500} max={12000} onCommit={(v) => apply({ op: 'set_stair', id: s.id, top_z: v })} />
      <Button size="sm" kind="tertiary"
        onClick={() => apply({ op: 'set_stair', id: s.id,
          flights: [...s.flights].reverse().map((f) => ({ ...f, start: f.end, end: f.start })) as SetStair['flights'] })}>
        Balik arah naik
      </Button>
      <DeleteWithReason id="cs-del" label="Hapus tangga" onDelete={(reason) => apply({ op: 'delete_stair', id: s.id, reason })} />
    </>
  )
}

function AddWallForm() {
  const draft = useEditorStore((s) => s.wallDraft)
  const setDraft = useEditorStore((s) => s.setWallDraft)
  const spec = useEditorStore((s) => s.wallSpec)
  const setSpec = useEditorStore((s) => s.setWallSpec)
  const pt = (k: 'a' | 'b', i: 0 | 1, v: number) => {
    const p = [...(draft[k] ?? [0, 0])] as Pt
    p[i] = v
    setDraft({ ...draft, [k]: p })
  }
  const { a, b } = draft
  return (
    <>
      <h5 className="editor-panel__sub">Tambah dinding</h5>
      <Button size="sm" kind="ghost" onClick={() => { const s = useEditorStore.getState(); s.setMode('top'); s.setTool('add-wall') }}>
        Klik dua titik
      </Button>
      <p className="helper">Enter: simpan dan lanjut dari titik akhir · Esc: berhenti</p>
      <div className="editor-grid2">
        <MmInput id="aw-ax" label="a.x (mm)" value={a?.[0]} min={-FAR} max={FAR} onCommit={(v) => pt('a', 0, v)} />
        <MmInput id="aw-ay" label="a.y (mm)" value={a?.[1]} min={-FAR} max={FAR} onCommit={(v) => pt('a', 1, v)} />
        <MmInput id="aw-bx" label="b.x (mm)" value={b?.[0]} min={-FAR} max={FAR} onCommit={(v) => pt('b', 0, v)} />
        <MmInput id="aw-by" label="b.y (mm)" value={b?.[1]} min={-FAR} max={FAR} onCommit={(v) => pt('b', 1, v)} />
      </div>
      <MmInput id="aw-t" label="Tebal dinding baru (mm)" value={spec.thickness} min={10} max={2000} onCommit={(thickness) => setSpec({ ...spec, thickness })} />
      <Dropdown id="aw-kind" titleText="Kind dinding baru" label="Kind" size="sm" items={[...KINDS]} selectedItem={spec.kind}
        onChange={({ selectedItem }) => setSpec({ ...spec, kind: selectedItem ?? 'partition' })} />
      <Button size="sm" kind="tertiary" disabled={!a || !b || (a[0] === b[0] && a[1] === b[1])}
        onClick={() => useEditorStore.getState().commitWallDraft()}>
        Tambah dinding
      </Button>
    </>
  )
}

/** Numeric geometry corrections (07 §6b); edits of unsaved elements fold or are refused with a notice by pushOp. */
export function CorrectionPanel() {
  const view = useEditorStore((s) => s.view)
  const selection = useEditorStore((s) => s.selection)
  if (!view) return null
  if (!selection.length) {
    return (
      <>
        <Button size="sm" kind="ghost" aria-label="Pilih dinding ragu (< 0.6)"
          onClick={() => { if (!useEditorStore.getState().selectDoubtfulWalls()) useEditorStore.getState().setNotice({ kind: 'info', text: 'Tidak ada dinding ragu' }) }}>
          Pilih dinding ragu (&lt; 0.6)
        </Button>
        <AddWallForm />
      </>
    )
  }
  const walls = selection.map((id) => view.walls?.find((w) => w.id === id)).filter((w): w is Wall => !!w)
  if (walls.length >= 2 && walls.length === selection.length) return <BulkWalls walls={walls} />
  if (selection.length !== 1) return null
  const id = selection[0]
  const w = view.walls?.find((x) => x.id === id), d = view.openings?.find((x) => x.id === id), s = view.stairs?.find((x) => x.id === id)
  if (w) return <WallForm key={id} w={w} />
  if (d) return <DoorForm key={id} d={d} />
  if (s) return <StairForm key={id} s={s} />
  return null
}
