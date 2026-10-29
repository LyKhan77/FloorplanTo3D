import { Button, Checkbox, ProgressBar } from '@carbon/react'
import { useEffect, useState } from 'react'
import type { ReviewTask } from '../../api/types'
import { useEditorStore } from '../store'
import { closeGapOps, DOOR_SKIPPED_TEXT } from './tools'

const GROUPS: [ReviewTask['kind'], string][] = [['gap', 'Celah terbuka'], ['leak', 'Ruang bocor'], ['loose', 'Dinding lepas'], ['type', 'Tipe ruang']]

/** M8 review: the located tasks of the paused spec; a task the latest dry run no longer reports is done. */
export function TasksPanel({ projectId, tasks }: { projectId: string; tasks: ReviewTask[] }) {
  const active = useEditorStore((s) => s.activeTask)
  const baseVersion = useEditorStore((s) => s.baseVersion)
  const withDoor = useEditorStore((s) => s.reviewWithDoor)
  // the list a review starts from: the first answer for this project and base version (derived state, set in render)
  const key = `${projectId}@${baseVersion}`
  const [start, setStart] = useState<{ key: string; tasks: ReviewTask[] }>({ key: '', tasks: [] })
  if (start.key !== key && tasks.length) setStart({ key, tasks })
  // the starting list plus any task an edit created since: the panel counts what the approve dialog counts
  const first = start.key === key ? start.tasks : tasks
  const all = [...first, ...tasks.filter((t) => !first.some((f) => f.id === t.id))]
  const open = new Set(tasks.map((t) => t.id))
  const done = all.filter((t) => !open.has(t.id)).length
  useEffect(() => { if (active && !open.has(active)) useEditorStore.getState().setActiveTask(null) })

  const focus = (t: ReviewTask) => {
    const s = useEditorStore.getState()
    s.setActiveTask(t.id)
    s.setFocus(t.at)
    if (t.kind === 'gap') { s.setTool('close-gap'); s.select([]) }
    else if (t.kind === 'leak') { s.setTool('guide-line'); s.select([]) }
    else { s.setTool('select'); s.select(t.element_ids) }
  }
  const close = (t: ReviewTask) => {
    const s = useEditorStore.getState()
    const r = closeGapOps(t, withDoor, s.view!)
    if (s.applyMany(r.ops) && r.doorSkipped) s.setNotice({ kind: 'info', text: DOOR_SKIPPED_TEXT[r.doorSkipped] })
  }

  return (
    <section className="editor-panel review-tasks" aria-label="Tugas review">
      <h4 className="editor-panel__title">Tugas review</h4>
      <p className="helper">{done} / {all.length} selesai</p>
      <ProgressBar label="Progres review" hideLabel value={all.length ? (done / all.length) * 100 : 100} size="small" />
      {GROUPS.map(([kind, title]) => {
        const items = all.filter((t) => t.kind === kind)
        if (!items.length) return null
        return (
          <div key={kind} className="review-tasks__group">
            <h5 className="editor-panel__sub">{title}</h5>
            {items.map((t) => {
              const finished = !open.has(t.id)
              return (
                <div key={t.id} className={`review-task${t.id === active ? ' is-active' : ''}${finished ? ' is-done' : ''}`}>
                  <button type="button" className="review-task__btn" disabled={finished} onClick={() => focus(t)}>
                    <span className="review-task__mark" aria-hidden="true">{finished ? '✓' : ''}</span>
                    <span>{t.message}</span>
                  </button>
                  {t.id === active && t.kind === 'gap' && !finished && (
                    <div className="review-task__tools">
                      <Checkbox id="gap-door" labelText="Pasang pintu" checked={withDoor} onChange={(_, { checked }) => useEditorStore.getState().setReviewWithDoor(checked)} />
                      <Button size="sm" kind="primary" onClick={() => close(t)}>Tutup celah</Button>
                    </div>
                  )}
                  {t.id === active && t.kind === 'leak' && !finished && (
                    <p className="helper">Tarik garis kasar di atas dinding yang hilang; sistem menempelkannya ke garis ganda di gambar.</p>
                  )}
                </div>
              )
            })}
          </div>
        )
      })}
    </section>
  )
}
