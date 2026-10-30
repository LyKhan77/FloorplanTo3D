import { create } from 'zustand'
import type { Installation } from '../types/installation'
import { applyInstallOps, type InstallOp } from './reducer'

type Pt = [number, number]
export type InstallTool = 'select' | 'tray' | 'rack'
export interface InstallNotice { kind: 'error' | 'warning' | 'info'; text: string }

interface State {
  /** whose installation `base` is (the store is shared by every project page) */
  projectId: string | null
  /** InstallEditor is on screen: the layout editor's shortcuts step aside */
  mounted: boolean
  setMounted(mounted: boolean): void
  base: Installation | null
  ops: InstallOp[]
  view: Installation | null
  past: InstallOp[][]
  future: InstallOp[][]
  selection: string[]
  tool: InstallTool
  trayDraft: Pt[]
  trayClass: 'data' | 'power'
  notice: InstallNotice | null
  /** the editor tab shows mode Instalasi */
  active: boolean
  setActive(active: boolean): void
  load(inst: Installation, projectId?: string): void
  apply(op: InstallOp): boolean
  applyMany(ops: InstallOp[]): boolean
  undo(): void
  redo(): void
  select(ids: string[]): void
  setTool(tool: InstallTool): void
  setTrayDraft(points: Pt[]): void
  setTrayClass(cls: 'data' | 'power'): void
  setNotice(n: InstallNotice | null): void
}

const UNDO_CAP = 100

/** The installation being edited (M12a): base version + pending ops, like the layout editor's store. */
export const useInstallStore = create<State>((set, get) => ({
  projectId: null, mounted: false, setMounted: (mounted) => set({ mounted }),
  base: null, ops: [], view: null, past: [], future: [], selection: [], tool: 'select', trayDraft: [], trayClass: 'data', notice: null, active: false,
  setActive: (active) => set({ active }),
  load: (inst, projectId) => set((s) => ({ projectId: projectId ?? s.projectId, base: inst, ops: [], view: inst, past: [], future: [], selection: [], trayDraft: [], notice: null })),
  apply: (op) => get().applyMany([op]),
  applyMany: (more) => {
    const { base, ops, past } = get()
    if (!base) return false
    const next = [...ops, ...more]
    const r = applyInstallOps(base, next)
    if (r.failed.length) {
      set({ notice: { kind: 'error', text: `${r.failed[0].op}: ${r.failed[0].message}` } })
      return false
    }
    set({ ops: next, view: r.inst, past: [...past, ops].slice(-UNDO_CAP), future: [], notice: null })
    return true
  },
  undo: () => {
    const { base, ops, past, future } = get()
    if (!base || !past.length) return
    const prev = past.at(-1)!
    set({ ops: prev, view: applyInstallOps(base, prev).inst, past: past.slice(0, -1), future: [ops, ...future] })
  },
  redo: () => {
    const { base, ops, past, future } = get()
    if (!base || !future.length) return
    const next = future[0]
    set({ ops: next, view: applyInstallOps(base, next).inst, past: [...past, ops], future: future.slice(1) })
  },
  select: (selection) => set({ selection }),
  setTool: (tool) => set({ tool, trayDraft: [] }),
  setTrayDraft: (trayDraft) => set({ trayDraft }),
  setTrayClass: (trayClass) => set({ trayClass }),
  setNotice: (notice) => set({ notice }),
}))
