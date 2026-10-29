import { ActionableNotification, Button, InlineNotification, Loading, ToastNotification } from '@carbon/react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useRegenerate } from '../api/hooks'
import type { Run } from '../api/types'
import { RebaseDialog } from './RebaseDialog'
import { StatusBar } from './StatusBar'
import { Toolbar } from './Toolbar'
import { geometryDiff, isEmptyDiff } from './lib/geometryDiff'
import { IssuesPanel } from './panels/IssuesPanel'
import { LayersPanel } from './panels/LayersPanel'
import { LibraryPanel } from './panels/LibraryPanel'
import { MeasurePanel } from './panels/MeasurePanel'
import { PropertiesPanel } from './panels/PropertiesPanel'
import { useEditorData } from './useEditorData'
import { useRegenerateFlow } from './useRegenerateFlow'
import { useSave } from './useSave'
import { useShortcuts } from './useShortcuts'
import { useValidate } from './useValidate'
import { ReviewCanvas } from './review/ReviewCanvas'
import { useBackdrop } from './review/useBackdrop'
import { useEditorStore } from './store'
import { Viewport } from './viewport/Viewport'

if (import.meta.env.DEV) (window as unknown as { __editor: typeof useEditorStore }).__editor = useEditorStore

export function EditorTab({ projectId, run }: { projectId: string; run: Run | null }) {
  const data = useEditorData(projectId)
  const regenerate = useRegenerate(projectId)
  const flow = useRegenerateFlow(projectId, run)
  const saver = useSave(projectId, flow.regenerate)
  const { save } = saver
  const onSave = useCallback(() => void save(), [save])
  useShortcuts(data.templates, onSave)
  const [left, setLeft] = useState(true)
  const [right, setRight] = useState(true)
  const notice = useEditorStore((s) => s.notice)
  const setNotice = useEditorStore((s) => s.setNotice)
  const previewBanner = useEditorStore((s) => s.previewBanner)
  const tool = useEditorStore((s) => s.tool)
  const mode = useEditorStore((s) => s.mode)
  const ops = useEditorStore((s) => s.ops)
  const baseVersion = useEditorStore((s) => s.baseVersion)
  const base = useEditorStore((s) => s.base)
  const view = useEditorStore((s) => s.view)
  const validation = useValidate(projectId, baseVersion, ops)
  const backdrop = useBackdrop(projectId)
  const geometryChanged = useMemo(() => !!base && !!view && !isEmptyDiff(geometryDiff(base, view)), [base, view])

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
      <Toolbar left={left} right={right} onToggleLeft={() => setLeft(!left)} onToggleRight={() => setRight(!right)}
        onSave={onSave} saving={saver.saving} onRegenerate={() => flow.regenerate()} regen={flow} />
      {saver.conflict && <RebaseDialog conflict={saver.conflict} onResolve={saver.resolve} />}
      {left && <aside className="editor__library" aria-label="Library template"><LibraryPanel templates={data.templates} /></aside>}
      <div className="editor__viewport">
        <div className="editor__banners">
        {data.stale && data.shellVersion !== null && (
          <InlineNotification kind="info" lowContrast hideCloseButton title=""
            subtitle={`Shell dari v${data.shellVersion}; regenerate untuk memperbarui`} />
        )}
        {previewBanner && (
          <InlineNotification kind="warning" lowContrast hideCloseButton title=""
            subtitle="Pratinjau: bukaan pintu belum akurat sampai regenerate" />
        )}
        {mode === 'walk' && (
          <InlineNotification kind="info" lowContrast hideCloseButton title=""
            subtitle="Walk: klik viewport untuk mulai, WASD/panah untuk jalan, Shift lari, Esc keluar" />
        )}
        {geometryChanged && (
          <InlineNotification kind="warning" lowContrast hideCloseButton title=""
            subtitle="Geometri berubah: Save + Regenerate untuk melihat hasil 3D" />
        )}
        </div>
        {notice?.action && (
          <ActionableNotification key={notice.text} className="editor__toast" kind={notice.kind} lowContrast inline
            title={notice.text} actionButtonLabel={notice.action.label}
            onActionButtonClick={() => { notice.action!.onClick(); setNotice(null) }} onClose={() => { setNotice(null); return false }} />
        )}
        {notice && !notice.action && (
          <ToastNotification key={notice.text} className="editor__toast" kind={notice.kind} lowContrast title={notice.text}
            timeout={notice.kind === 'error' ? 0 : 5000} onClose={() => { setNotice(null); return false }} />
        )}
        {data.shellUrl === null || mode === 'plan' ? (
          // M8: the 2D review canvas works before any 3D shell exists (a run paused for review has none yet)
          <div className="editor__canvas editor__canvas--plan">
            {data.shellUrl === null && run?.status !== 'needs_review' && (
              <div className="editor__plan-note">
                <span>Belum ada shell 3D.</span>
                <Button size="sm" kind="ghost" disabled={regenerate.isPending} onClick={() => regenerate.mutate('HEAD')}>Regenerate</Button>
              </div>
            )}
            <ReviewCanvas rooms={validation.rooms ?? view?.rooms ?? []} tasks={validation.tasks} backdrop={backdrop} />
          </div>
        ) : <div className="editor__canvas"><Viewport shellUrl={data.shellUrl} templates={data.templates} /></div>}
      </div>
      {right && <aside className="editor__props" aria-label="Properti">{tool === 'select' || tool === 'add-wall' ? <PropertiesPanel templates={data.templates} /> : <MeasurePanel />}
        <IssuesPanel issues={validation.issues} newIssues={validation.newIssues}
          extra={validation.error ? [{ code: 'bad_op', severity: 'error', element_ids: [], message: validation.error }] : []} />
        <LayersPanel /></aside>}
      <StatusBar />
    </div>
  )
}
