import { Button, InlineLoading, TextInput } from '@carbon/react'
import { useEffect, useRef, useState } from 'react'
import { useInstallStore } from '../../install/store'
import { useEditorStore } from '../store'
import { useAssistStore, type Msg } from './store'

const m = (mm: number) => (mm / 1000).toFixed(1).replace('.', ',')

/** The chat of "Perbaiki area" (tool A): instruction, streamed steps, questions, the proposal and Terima/Tolak. */
export function AssistPanel({ projectId }: { projectId: string }) {
  const { box, messages, pending, proposal, send, accept, reject, close } = useAssistStore()
  const selection = useEditorStore((s) => s.selection)
  const [text, setText] = useState('')
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { end.current?.scrollIntoView?.({ block: 'end' }) }, [messages.length])

  const submit = () => {
    if (!text.trim() || pending) return
    void send(projectId, text.trim())
    setText('')
  }
  const quit = () => {
    const layer = useAssistStore.getState().layer
    close()
    if (layer === 'installation') useInstallStore.getState().setTool('select')
    else useEditorStore.getState().setTool('select')
  }

  return (
    <section className="editor-panel assist" aria-label="Perbaiki area">
      <div className="assist__head">
        <h4 className="editor-panel__title">Perbaiki area</h4>
        <Button kind="ghost" size="sm" onClick={quit}>Tutup (Esc)</Button>
      </div>
      {!box ? <p className="helper">Tarik kotak di kanvas di sekitar area yang salah. Elemen yang sedang terpilih ikut dikirim sebagai rujukan "ini".</p> : (
        <p className="helper">Area {m(box[2] - box[0])} × {m(box[3] - box[1])} m{selection.length ? ` · terpilih: ${selection.join(', ')}` : ''}</p>
      )}
      <div className="assist__log" aria-live="polite">
        {messages.map((msg, i) => <Message key={i} msg={msg} live={msg.role === 'proposal' && msg.proposal === proposal}
          onAccept={() => accept(projectId)} onReject={() => reject(projectId)} />)}
        {pending && <InlineLoading description="Strata bekerja…" />}
        <div ref={end} />
      </div>
      {box && (
        <form className="assist__compose" onSubmit={(e) => { e.preventDefault(); submit() }}>
          <TextInput id="assist-input" labelText="Instruksi" hideLabel size="sm" value={text} disabled={pending}
            placeholder='Contoh: "gabungkan dinding dobel", "hapus ini", "tambah pintu di sini"'
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Escape') quit() }} />
          <Button type="submit" size="sm" disabled={pending || !text.trim()}>Kirim</Button>
        </form>
      )}
    </section>
  )
}

function Message({ msg, live, onAccept, onReject }: { msg: Msg; live: boolean; onAccept(): void; onReject(): void }) {
  if (msg.role !== 'proposal') return <p className={`assist__msg assist__msg--${msg.role}`}>{msg.text}</p>
  const p = msg.proposal
  return (
    <div className={`assist__proposal assist__proposal--${msg.state}`}>
      <span className="helper">Usulan · {p.ops.length} op{msg.state !== 'open' ? ` · ${STATE[msg.state]}` : ''}</span>
      <p>{p.explanation}</p>
      {[...p.notes, ...p.issues.map((i) => `${i.code}: ${i.message}`)].map((n, i) => <p key={i} className="assist__note">{n}</p>)}
      {live && (
        <div className="assist__actions">
          <Button size="sm" disabled={!p.valid} onClick={onAccept}>Terima</Button>
          <Button size="sm" kind="secondary" onClick={onReject}>Tolak</Button>
          {!p.valid && <span className="assist__note">Terima nonaktif: usulan tidak valid (lihat catatan). Balas untuk merevisi.</span>}
        </div>
      )}
    </div>
  )
}

const STATE = { accepted: 'diterima', rejected: 'ditolak', stale: 'usang', revised: 'direvisi' }
