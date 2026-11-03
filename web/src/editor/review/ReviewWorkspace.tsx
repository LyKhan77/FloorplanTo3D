import { useEffect, useState } from 'react'
import { ignoredTarget } from '../lib/keys'
import type { Tool } from '../store'
import type { Backdrop, ReviewTask } from '../../api/types'
import type { Room } from '../../types/spec'
import { useEditorStore } from '../store'
import { svgPoint } from './planTransform'
import { ReviewCanvas } from './ReviewCanvas'
import { closeGapOps, doorOps, DOOR_SKIPPED_TEXT, snapGuide } from './tools'
import { ProposalLayer } from '../assist/ProposalLayer'
import { useAssistStore } from '../assist/store'
import { drawnBox } from '../assist/stream'
import { ApiError } from '../../api/client'

type Pt = [number, number]

/** The review canvas with its tools: gap handles (click both ends to close) and the snapped guide line. */
export function ReviewWorkspace({ projectId, rooms, tasks, backdrop }: {
  projectId: string; rooms: Room[]; tasks: ReviewTask[]; backdrop: Backdrop | null
}) {
  const tool = useEditorStore((s) => s.tool)
  const active = useEditorStore((s) => s.activeTask)
  // handles picked for the active task only: a new task starts with none (derived, no effect)
  const [pickedFor, setPickedFor] = useState<{ task: string | null; ids: number[] }>({ task: null, ids: [] })
  const picked = pickedFor.task === active ? pickedFor.ids : []
  const [rough, setRough] = useState<{ a: Pt; b: Pt } | null>(null)
  const task = tasks.find((t) => t.id === active)

  const pickHandle = (i: number) => {
    const next = [...new Set([...picked, i])]
    setPickedFor({ task: active, ids: next })
    if (next.length === 2 && task) {
      const s = useEditorStore.getState()
      const r = closeGapOps(task, s.reviewWithDoor, s.view!)
      if (s.applyMany(r.ops) && r.doorSkipped) s.setNotice({ kind: 'info', text: DOOR_SKIPPED_TEXT[r.doorSkipped] })
    }
  }
  const onPointer = (kind: 'down' | 'move' | 'up', mm: Pt, e: React.PointerEvent) => {
    if (tool === 'assist' && e.button <= 0) {
      // "Perbaiki area": drag a box; the chat panel on the right takes the instruction
      if (kind === 'down') setRough({ a: mm, b: mm })
      else if (kind === 'move' && rough) setRough({ ...rough, b: mm })
      else if (kind === 'up' && rough) {
        const [a, b] = [rough.a, mm]
        setRough(null)
        const dragged = Math.abs(b[0] - a[0]) > 300 && Math.abs(b[1] - a[1]) > 300
        if (dragged && !e.shiftKey) {
          useAssistStore.getState().open([Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[0], b[0]), Math.max(a[1], b[1])].map(Math.round) as [number, number, number, number])
        } else if (dragged || Math.hypot(b[0] - a[0], b[1] - a[1]) < 300) {
          // a click points at drawn equipment (K1, K2, ...); Shift-drag fits a box to the drawn lines
          const at = dragged ? { a: a.map(Math.round) as Pt, b: b.map(Math.round) as Pt } : { at: b.map(Math.round) as Pt }
          drawnBox(projectId, at).then((found) => {
            const s = useAssistStore.getState()
            if (!s.box) s.open(boxAround(found.center, found.size))
            s.addDrawn(found)
          }).catch((err) => {
            if (err instanceof ApiError && err.code === 'no_box') return  // a click on empty floor or a wall: just a selection
            useEditorStore.getState().setNotice({ kind: 'warning', text: err instanceof Error ? err.message : String(err) })
          })
        }
      }
      return true
    }
    if (tool === 'add-wall' && e.button <= 0) {
      // the 2D canvas draws walls too (a paused run has no 3D shell): click, click, chained; Esc stops
      if (kind === 'up') {
        const s = useEditorStore.getState(), p: Pt = [Math.round(mm[0] / 100) * 100, Math.round(mm[1] / 100) * 100]
        if (!s.wallDraft.a) s.setWallDraft({ a: p })
        else { s.setWallDraft({ a: s.wallDraft.a, b: p }); s.commitWallDraft() }
      }
      return true
    }
    if ((tool !== 'guide-line' && tool !== 'add-door') || e.button > 0) return false
    if (kind === 'down') setRough({ a: mm, b: mm })
    else if (kind === 'move' && rough) setRough({ ...rough, b: mm })
    else if (kind === 'up') {
      const a = rough?.a ?? mm
      setRough(null)
      if (tool === 'add-door') {
        // a click places a 900 mm door; a line from jamb to jamb is the door (on a wall, over a door, or across a gap)
        const s = useEditorStore.getState(), r = doorOps(s.view!, a, mm, s.wallSpec.thickness)
        if ('error' in r) s.setNotice({ kind: 'warning', text: r.error })
        else s.applyMany(r.ops)
      } else if (Math.hypot(mm[0] - a[0], mm[1] - a[1]) > 300) void snapGuide(projectId, a, mm)
    }
    return true
  }

  const draft = useEditorStore((s) => s.wallDraft)
  // leaving the tool ends the session: its box and proposal belong to the canvas state it was made on
  useEffect(() => { if (tool !== 'assist') useAssistStore.getState().close() }, [tool])
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (ignoredTarget(e.target as Element | null)) return
      const s = useEditorStore.getState()
      if (e.key === 'Escape') { s.setWallDraft({}); s.setTool('select'); setRough(null); return }
      const t = ({ v: 'select', l: 'guide-line', w: 'add-wall', d: 'add-door', a: 'assist' } as Record<string, Tool>)[e.key.toLowerCase()]
      if (t && !e.ctrlKey && !e.metaKey && !e.altKey) s.setTool(t)
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [])

  return (
    <>
    <div className="review-tools" role="toolbar" aria-label="Alat review">
      {REVIEW_TOOLS.map(([t, label, k]) => (
        <button key={t} type="button" aria-label={label} aria-pressed={tool === t} className={tool === t ? 'is-on' : undefined}
          onClick={() => useEditorStore.getState().setTool(t)}>{label} <kbd>{k}</kbd></button>
      ))}
    </div>
    <ReviewCanvas rooms={rooms} tasks={tasks} backdrop={backdrop} onCanvasPointer={onPointer}>
      {tool === 'close-gap' && task?.kind === 'gap' && [task.fix.a, task.fix.b].map((p, i) => {
        if (!p) return null
        const [x, y] = svgPoint(p)
        return <circle key={i} data-handle={i} cx={x} cy={y} r={160} className={`review-handle${picked.includes(i) ? ' is-picked' : ''}`}
          onClick={(e) => { e.stopPropagation(); pickHandle(i) }} />
      })}
      {tool === 'assist' && <ProposalLayer draft={rough ? [rough.a, rough.b] : null} />}
      {rough && tool !== 'assist' && (() => {
        const [a, b] = [svgPoint(rough.a), svgPoint(rough.b)]
        return <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={tool === 'add-door' ? '#ff832b' : '#42be65'} strokeWidth={80} strokeDasharray="200 120" />
      })()}
      {tool === 'add-wall' && draft.a && (() => {
        const [x, y] = svgPoint(draft.a)
        return <circle cx={x} cy={y} r={120} fill="#42be65" style={{ pointerEvents: 'none' }} />
      })()}
    </ReviewCanvas>
    </>
  )
}

/** An area around a pointed box when no area was marked yet: the chat needs one. */
function boxAround(c: Pt, size: [number, number]): [number, number, number, number] {
  const r = size[1] / 2 + 1500
  return [c[0] - r, c[1] - r, c[0] + r, c[1] + r].map(Math.round) as [number, number, number, number]
}

const REVIEW_TOOLS: [Tool, string, string][] = [['select', 'Pilih', 'V'], ['guide-line', 'Garis bantu', 'L'], ['add-wall', 'Dinding baru', 'W'], ['add-door', 'Pintu', 'D'], ['assist', 'Perbaiki area', 'A']]
