import { create } from 'zustand'
import { ApiError } from '../../api/client'
import { useInstallStore } from '../../install/store'
import type { InstallOp } from '../../install/reducer'
import type { EditorOp } from '../ops/reducer'
import { useEditorStore } from '../store'
import { postDecision, streamAssist, type DrawnBox, type Proposal } from './stream'

export type Box = [number, number, number, number]
export type Msg =
  | { role: 'user' | 'step' | 'question' | 'error' | 'info'; text: string }
  | { role: 'proposal'; proposal: Proposal; state: 'open' | 'accepted' | 'rejected' | 'stale' | 'revised' }

export type AssistLayer = 'layout' | 'installation'

interface AssistState {
  /** layout: the chat edits the architecture (editor store); installation: the equipment (install store) */
  layer: AssistLayer
  setLayer(layer: AssistLayer): void
  box: Box | null
  drawn: DrawnBox[]  // boxes pointed at in the drawing this session: K1, K2, ...
  addDrawn(b: Omit<DrawnBox, 'id'>): string
  sessionId: string | null
  messages: Msg[]
  pending: boolean
  proposal: Proposal | null
  baseKey: string | null  // the editor's base version + local ops the proposal was made on
  open(box: Box): void
  close(): void
  send(projectId: string, text: string): Promise<void>
  accept(projectId: string): void
  reject(projectId: string): void
}

const STALE = 'Usulan usang, kirim ulang: denah berubah sejak usulan dibuat.'
/** The store the chat edits: its base version, pending ops, selection, and how a proposal is applied. */
function target(layer: AssistLayer) {
  if (layer === 'installation') {
    const s = useInstallStore.getState()
    return { base: s.base?.meta.version ?? null, ops: s.ops as unknown[], selection: s.selection,
      apply: (ops: unknown[]) => s.applyMany(ops as InstallOp[]) }
  }
  const s = useEditorStore.getState()
  return { base: s.baseVersion, ops: s.ops as unknown[], selection: s.selection,
    apply: (ops: unknown[]) => s.applyMany(ops as EditorOp[]) }
}
const editorKey = (layer: AssistLayer) => { const t = target(layer); return JSON.stringify([t.base, t.ops]) }

/** One area-assist session (design §6.6): the marked box, the chat, and the open proposal. */
export const useAssistStore = create<AssistState>()((set, get) => {
  const push = (m: Msg) => set((s) => ({ messages: [...s.messages, m] }))
  const settle = (state: 'accepted' | 'rejected' | 'stale' | 'revised') => set((s) => ({
    proposal: null,
    messages: s.messages.map((m) => (m.role === 'proposal' && m.proposal === s.proposal ? { ...m, state } : m)),
  }))
  const decide = (projectId: string, accepted: boolean) => {
    const sid = get().sessionId
    if (sid) postDecision(projectId, sid, accepted).catch(() => {})  // the log is best effort; the edit already happened
  }
  return {
    layer: 'layout', setLayer: (layer) => { if (layer !== get().layer) set({ layer, box: null, drawn: [], sessionId: null, messages: [], proposal: null, baseKey: null }) },
    box: null, drawn: [], sessionId: null, messages: [], pending: false, proposal: null, baseKey: null,
    addDrawn: (b) => {
      // the same drawn box clicked again (within 50 mm): keep its K
      const same = get().drawn.find((k) => Math.hypot(k.center[0] - b.center[0], k.center[1] - b.center[1]) < 50)
      if (same) return same.id
      const id = `K${get().drawn.length + 1}`
      set((s) => ({ drawn: [...s.drawn, { ...b, id }] }))
      return id
    },
    // a new box keeps the conversation: "now this area too" is a follow-up
    open: (box) => set({ box, proposal: null }),
    close: () => set({ box: null, drawn: [], sessionId: null, messages: [], pending: false, proposal: null, baseKey: null }),
    send: async (projectId, text) => {
      const { box, sessionId, pending } = get()
      const layer = get().layer
      const ed = target(layer)
      if (!box || pending || !text.trim() || ed.base === null) return
      // a message while a proposal is open answers it: the server logs it as a revision, nothing was applied
      if (get().proposal) settle('revised')
      const baseKey = editorKey(layer)
      push({ role: 'user', text })
      set({ pending: true })
      try {
        await streamAssist(projectId, {
          ...(sessionId ? { session_id: sessionId } : {}), base_version: ed.base, ops: ed.ops as EditorOp[], box,
          selection: ed.selection, message: text, drawn: get().drawn, layer,
        }, (e) => {
          if (e.event === 'session') set({ sessionId: e.session_id })
          else if (e.event === 'step' || e.event === 'question' || e.event === 'error') push({ role: e.event, text: e.text })
          else if (e.event === 'proposal') {
            const { event: _, ...proposal } = e
            set({ proposal, baseKey })
            push({ role: 'proposal', proposal, state: 'open' })
          }
        })
      } catch (err) {
        if (err instanceof ApiError && err.code === 'no_session') set({ sessionId: null })
        push({ role: 'error', text: err instanceof Error ? err.message : 'Gagal menghubungi server' })
      } finally {
        set({ pending: false })
      }
    },
    accept: (projectId) => {
      const { proposal, baseKey } = get()
      if (!proposal?.valid) return
      const layer = get().layer
      if (editorKey(layer) !== baseKey || !target(layer).apply(proposal.ops)) {
        settle('stale')
        push({ role: 'error', text: STALE })
        return
      }
      settle('accepted')
      push({ role: 'info', text: `Diterapkan: ${proposal.ops.length} op masuk ke perubahan belum disimpan (satu langkah undo).` })
      decide(projectId, true)
    },
    reject: (projectId) => {
      if (!get().proposal) return
      settle('rejected')
      push({ role: 'info', text: 'Ditolak. Tidak ada yang berubah.' })
      decide(projectId, false)
    },
  }
})
