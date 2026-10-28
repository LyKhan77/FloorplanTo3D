import { create } from 'zustand'
import type { Template } from '../api/types'
import type { Spec, Wall } from '../types/spec'
import { pushOp } from './ops/compose'
import { allIds } from './ops/ids'
import { applyOps, type EditorOp, type OpFailure } from './ops/reducer'

export type Tool = 'select' | 'distance' | 'room-area' | 'area' | 'height' | 'add-wall'
export type Mode = 'orbit' | 'top' | 'walk'
export type Gizmo = 'translate' | 'rotate' | 'scale'
export type Layer = 'walls' | 'columns' | 'doors' | 'objects' | 'labels' | 'grid' | 'axes'
export type Point3 = [number, number, number]
export interface Measurement {
  id: string
  kind: 'distance' | 'room-area' | 'area' | 'height'
  points: Point3[]
  value: number
  label: string
}
export interface Issue { code: string; severity: 'error' | 'warning' | 'info'; element_ids: string[]; message: string }
export interface Notice { kind: 'error' | 'warning' | 'info'; text: string; action?: { label: string; onClick(): void } }

const UNDO_CAP = 100

interface EditorState {
  projectId: string | null
  baseVersion: number | null
  base: Spec | null
  ops: EditorOp[]
  past: EditorOp[][]
  future: EditorOp[][]
  view: Spec | null
  failed: OpFailure[]
  selection: string[]
  tool: Tool
  mode: Mode
  snap: boolean
  layers: Record<Layer, boolean>
  cutaway: number | null
  measurements: Measurement[]
  notice: Notice | null
  saveIssues: Issue[]
  cursor: [number, number] | null
  hoverRoom: string | null
  fps: number | null
  previewBanner: boolean
  missingTemplates: string[]
  dragging: Template | null
  gizmo: Gizmo
  wallDraft: { a?: [number, number]; b?: [number, number] }
  wallSpec: { thickness: number; kind: Wall['kind'] }
  focus: [number, number] | null
  saving: boolean
  load(projectId: string, spec: Spec): void
  apply(op: EditorOp): boolean
  applyMany(ops: EditorOp[]): boolean
  undo(): void
  redo(): void
  select(ids: string[], additive?: boolean): void
  setTool(tool: Tool): void
  setMode(mode: Mode): void
  toggleLayer(layer: Layer): void
  setSnap(on: boolean): void
  setCutaway(mm: number | null): void
  addMeasurement(m: Measurement): void
  removeMeasurement(id: string): void
  clearMeasurements(): void
  markSaved(spec: Spec): void
  acceptRebase(head: Spec, drop: number[]): void
  setNotice(n: Notice | null): void
  setSaveIssues(issues: Issue[]): void
  setCursor(cursor: [number, number] | null, hoverRoom: string | null): void
  setFps(fps: number): void
  setPreviewBanner(on: boolean): void
  setMissingTemplates(objectIds: string[]): void
  setDragging(t: Template | null): void
  setGizmo(g: Gizmo): void
  setWallDraft(d: { a?: [number, number]; b?: [number, number] }): void
  setWallSpec(w: { thickness: number; kind: Wall['kind'] }): void
  commitWallDraft(): boolean
  setFocus(p: [number, number] | null): void
  takeFocus(): [number, number] | null
  setSaving(on: boolean): void
}

const LAYERS: Record<Layer, boolean> = {
  walls: true, columns: true, doors: true, objects: true, labels: true, grid: true, axes: false,
}

/** view/failed are computed here, on every ops change, so components read finished values. */
function derived(base: Spec, ops: EditorOp[], selection: string[]) {
  const { spec, failed } = applyOps(base, ops)
  const ids = new Set(allIds(spec))
  return { ops, view: spec, failed, selection: selection.filter((id) => ids.has(id)) }
}

function fresh(spec: Spec) {
  return { base: spec, baseVersion: spec.meta.version ?? null, ops: [], past: [], future: [], view: spec, failed: [],
    saveIssues: [] }
}

export const useEditorStore = create<EditorState>()((set, get) => {
  function commit(next: EditorOp[]): boolean {
    const { base, ops, past, failed, selection } = get()
    const d = derived(base!, next, selection)
    if (d.failed.length > failed.length) {
      const f = d.failed.find((x) => !failed.some((p) => p.op === x.op && p.message === x.message)) ?? d.failed[0]
      set({ notice: { kind: 'error', text: `${f.op}: ${f.message}` } })
      return false
    }
    set({ ...d, past: [...past, ops].slice(-UNDO_CAP), future: [], notice: null })
    return true
  }

  return {
    projectId: null, baseVersion: null, base: null, ops: [], past: [], future: [], view: null, failed: [],
    selection: [], tool: 'select', mode: 'orbit', snap: true, layers: { ...LAYERS }, cutaway: null,
    measurements: [], notice: null, saveIssues: [], cursor: null, hoverRoom: null, fps: null,
    previewBanner: false, missingTemplates: [], dragging: null, gizmo: 'translate', wallDraft: {}, wallSpec: { thickness: 150, kind: 'partition' }, focus: null,
    saving: false,

    load: (projectId, spec) => set({ ...fresh(spec), projectId, selection: [], measurements: [], notice: null, wallDraft: {},
      wallSpec: { thickness: spec.meta.defaults?.wall_thickness ?? 150, kind: 'partition' } }),
    apply: (op) => get().applyMany([op]),
    applyMany: (list) => {
      const { base, saving } = get()
      if (!base) return false
      // markSaved replaces the op list with the server's answer; an edit made meanwhile would vanish
      if (saving) {
        set({ notice: { kind: 'warning', text: 'Sedang menyimpan; tunggu sebentar' } })
        return false
      }
      let next = get().ops
      for (const op of list) {
        const r = pushOp(base, next, op)
        if ('error' in r) {
          set({ notice: { kind: 'error', text: r.error } })
          return false
        }
        next = r.ops
      }
      return next === get().ops || commit(next)
    },
    undo: () => {
      const { base, ops, past, future, selection } = get()
      if (!base || !past.length || get().saving) return
      set({ ...derived(base, past.at(-1)!, selection), past: past.slice(0, -1), future: [ops, ...future] })
    },
    redo: () => {
      const { base, ops, past, future, selection } = get()
      if (!base || !future.length || get().saving) return
      set({ ...derived(base, future[0], selection), past: [...past, ops], future: future.slice(1) })
    },
    select: (ids, additive) => set((s) => ({ selection: additive ? [...new Set([...s.selection, ...ids])] : ids })),
    setTool: (tool) => set({ tool }),
    setMode: (mode) => set({ mode }),
    toggleLayer: (layer) => set((s) => ({ layers: { ...s.layers, [layer]: !s.layers[layer] } })),
    setSnap: (snap) => set({ snap }),
    setCutaway: (cutaway) => set({ cutaway }),
    addMeasurement: (m) => set((s) => ({ measurements: [...s.measurements, m] })),
    removeMeasurement: (id) => set((s) => ({ measurements: s.measurements.filter((m) => m.id !== id) })),
    clearMeasurements: () => set({ measurements: [] }),
    markSaved: (spec) => set((s) => ({ ...fresh(spec), selection: derived(spec, [], s.selection).selection })),
    acceptRebase: (head, drop) => {
      const { ops, selection, base } = get()
      const kept = ops.filter((_, i) => !drop.includes(i))
      // a predicted id may now name the other tab's new element: keep only ids the old base had
      const known = new Set(base ? allIds(base) : [])
      set({ ...fresh(head), ...derived(head, kept, selection.filter((id) => known.has(id))) })
    },
    setNotice: (notice) => set({ notice }),
    setSaveIssues: (saveIssues) => set({ saveIssues }),
    setCursor: (cursor, hoverRoom) => set({ cursor, hoverRoom }),
    setFps: (fps) => set({ fps }),
    setPreviewBanner: (previewBanner) => set({ previewBanner }),
    setMissingTemplates: (missingTemplates) => set({ missingTemplates }),
    setDragging: (dragging) => set({ dragging }),
    setGizmo: (gizmo) => set({ gizmo }),
    setWallDraft: (wallDraft) => set({ wallDraft }),
    setWallSpec: (wallSpec) => set({ wallSpec }),
    commitWallDraft: () => {
      const { wallDraft: { a, b }, wallSpec, apply } = get()
      if (!a || !b || (a[0] === b[0] && a[1] === b[1])) return false
      if (!apply({ op: 'add_wall', a, b, ...wallSpec })) return false
      // chained drawing: the next wall starts where this one ended
      set({ wallDraft: { a: b } })
      return true
    },
    setFocus: (focus) => set({ focus }),
    setSaving: (saving) => set({ saving }),
    takeFocus: () => {
      const { focus } = get()
      if (focus) set({ focus: null })
      return focus
    },
  }
})
