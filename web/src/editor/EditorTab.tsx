import { Button, InlineNotification, Loading } from '@carbon/react'
import { useEffect, useState } from 'react'
import { useRegenerate } from '../api/hooks'
import type { Run } from '../api/types'
import { StatusBar } from './StatusBar'
import { Toolbar } from './Toolbar'
import { useEditorData } from './useEditorData'
import { useEditorStore } from './store'

if (import.meta.env.DEV) (window as unknown as { __editor: typeof useEditorStore }).__editor = useEditorStore

export function EditorTab({ projectId, run }: { projectId: string; run: Run | null }) {
  const data = useEditorData(projectId)
  const regenerate = useRegenerate(projectId)
  const [left, setLeft] = useState(true)
  const [right, setRight] = useState(true)
  const notice = useEditorStore((s) => s.notice)
  const setNotice = useEditorStore((s) => s.setNotice)
  void run // consumed by Save/Regenerate (Task 13)

  // Load HEAD once per project; a refetch never discards local ops (a newer HEAD is handled by Save's rebase).
  useEffect(() => {
    const spec = data.spec
    if (!spec) return
    const s = useEditorStore.getState()
    if (s.projectId !== projectId || (!s.ops.length && s.baseVersion !== (spec.meta.version ?? null))) s.load(projectId, spec)
  }, [projectId, data.spec])

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (!useEditorStore.getState().ops.length) return
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [])

  if (data.loading) return <Loading withOverlay={false} description="Memuat editor" />
  if (!data.spec) return <p className="helper">Belum ada spec. Impor spec dulu.</p>

  const cls = ['editor', left ? '' : 'editor--no-left', right ? '' : 'editor--no-right'].filter(Boolean).join(' ')
  return (
    <div className={cls}>
      <Toolbar left={left} right={right} onToggleLeft={() => setLeft(!left)} onToggleRight={() => setRight(!right)} />
      {left && <aside className="editor__library" aria-label="Library template" />}
      <div className="editor__viewport">
        {data.stale && data.shellVersion !== null && (
          <InlineNotification kind="info" lowContrast hideCloseButton title=""
            subtitle={`Shell dari v${data.shellVersion}; regenerate untuk memperbarui`} />
        )}
        {notice && (
          <InlineNotification kind={notice.kind} lowContrast title="" subtitle={notice.text} onClose={() => setNotice(null)} />
        )}
        {data.shellUrl === null ? (
          <div className="editor__empty">
            <p>Belum ada shell. Regenerate dulu.</p>
            <Button size="sm" disabled={regenerate.isPending} onClick={() => regenerate.mutate('HEAD')}>Regenerate</Button>
          </div>
        ) : <div className="editor__canvas" />}
      </div>
      {right && <aside className="editor__props" aria-label="Properti" />}
      <StatusBar />
    </div>
  )
}
