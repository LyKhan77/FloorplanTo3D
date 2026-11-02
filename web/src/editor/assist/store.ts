import { create } from 'zustand'
import { ApiError } from '../../api/client'
import { useEditorStore } from '../store'
import { postDecision, streamAssist, type Proposal } from './stream'

export type Box = [number, number, number, number]
export type Msg =
  | { role: 'user' | 'step' | 'question' | 'error' | 'info'; text: string }
  | { role: 'proposal'; proposal: Proposal; state: 'open' | 'accepted' | 'rejected' | 'stale' }

interface AssistState {
  box: Box | null
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
const editorKey = () => { const s = useEditorStore.getState(); return JSON.stringify([s.baseVersion, s.ops]) }

/** One area-assist session (design §6.6): the marked box, the chat, and the open proposal. */
export const useAssistStore = create<AssistState>()((set, get) => {
  const push = (m: Msg) => set((s) => ({ messages: [...s.messages, m] }))
  const settle = (state: 'accepted' | 'rejected' | 'stale') => set((s) => ({
    proposal: null,
    messages: s.messages.map((m) => (m.role === 'proposal' && m.proposal === s.proposal ? { ...m, state } : m)),
  }))
  const decide = (projectId: string, accepted: boolean) => {
    const sid = get().sessionId
    if (sid) postDecision(projectId, sid, accepted).catch(() => {})  // the log is best effort; the edit already happened
  }
  return {
    box: null, sessionId: null, messages: [], pending: false, proposal: null, baseKey: null,
    // a new box keeps the conversation: "now this area too" is a follow-up
    open: (box) => set({ box, proposal: null }),
    close: () => set({ box: null, sessionId: null, messages: [], pending: false, proposal: null, baseKey: null }),
    send: async (projectId, text) => {
      const { box, sessionId, pending } = get()
      const ed = useEditorStore.getState()
      if (!box || pending || !text.trim() || ed.baseVersion === null) return
      if (get().proposal) settle('rejected')
      const baseKey = editorKey()
      push({ role: 'user', text })
      set({ pending: true })
      try {
        await streamAssist(projectId, {
          ...(sessionId ? { session_id: sessionId } : {}), base_version: ed.baseVersion, ops: ed.ops, box,
          selection: ed.selection, message: text,
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
      if (editorKey() !== baseKey || !useEditorStore.getState().applyMany(proposal.ops)) {
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
