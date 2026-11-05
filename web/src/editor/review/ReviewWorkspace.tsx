import { useEffect, useRef, useState } from 'react'
import { ignoredTarget } from '../lib/keys'
import type { Tool } from '../store'
import type { Backdrop, ReviewTask } from '../../api/types'
import type { Room } from '../../types/spec'
import { useEditorStore } from '../store'
import { svgPoint } from './planTransform'
import { ReviewCanvas } from './ReviewCanvas'
import { closeGapOps, doorOps, DOOR_SKIPPED_TEXT, snapGuide, stairOps } from './tools'
import { ProposalLayer } from '../assist/ProposalLayer'
import { useAssistStore } from '../assist/store'
import { areaPointer } from '../assist/areaPointer'

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
  const [stairPath, setStairPath] = useState<Pt[]>([])
  const [stairCursor, setStairCursor] = useState<Pt | null>(null)
  const finishStair = (path: Pt[]) => {
    const s = useEditorStore.getState()
    const ops = stairOps(path, s.view?.meta.defaults?.floor_to_floor ?? DEFAULT_FLOOR_TO_FLOOR_MM)
    if (ops.length) s.applyMany(ops)
    else s.setNotice({ kind: 'warning', text: 'Klik jalur tangga dari bawah ke atas; ruas harus minimal 2,4 m' })
    setStairPath([])
    setStairCursor(null)
  }
  const onPointer = (kind: 'down' | 'move' | 'up', mm: Pt, e: React.PointerEvent) => {
    if (tool === 'assist' && e.button <= 0) return areaPointer(projectId, kind, mm, e, rough, setRough)
    if (tool === 'add-wall' && e.button <= 0) {
      // the 2D canvas draws walls too (a paused run has no 3D shell): click, click, chained; Esc stops
      if (kind === 'up') {
        const s = useEditorStore.getState(), p: Pt = [Math.round(mm[0] / 100) * 100, Math.round(mm[1] / 100) * 100]
        if (!s.wallDraft.a) s.setWallDraft({ a: p })
        else { s.setWallDraft({ a: s.wallDraft.a, b: p }); s.commitWallDraft() }
      }
      return true
    }
    if (tool === 'add-stair' && e.button <= 0) {
      const p: Pt = [Math.round(mm[0] / 100) * 100, Math.round(mm[1] / 100) * 100]
      if (kind === 'move') setStairCursor(p)
      else if (kind === 'up') {
        const last = stairPath.at(-1)
        if (last && last[0] === p[0] && last[1] === p[1]) finishStair(stairPath)  // a second click on the same spot
        else setStairPath([...stairPath, p])
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

  const enterStair = useRef(() => {})
  useEffect(() => { enterStair.current = () => { if (stairPath.length) finishStair(stairPath) } })
  const draft = useEditorStore((s) => s.wallDraft)
  // leaving the tool ends the session: its box and proposal belong to the canvas state it was made on
  useEffect(() => {
    if (tool === 'assist') useAssistStore.getState().setLayer('layout')
    else useAssistStore.getState().close()
  }, [tool])
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (ignoredTarget(e.target as Element | null)) return
      const s = useEditorStore.getState()
      if (e.key === 'Escape') { s.setWallDraft({}); s.setTool('select'); setRough(null); setStairPath([]); setStairCursor(null); return }
      if (e.key === 'Enter') { enterStair.current(); return }
      const t = ({ v: 'select', l: 'guide-line', w: 'add-wall', d: 'add-door', s: 'add-stair', a: 'assist' } as Record<string, Tool>)[e.key.toLowerCase()]
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
      {tool === 'add-stair' && stairPath.length > 0 && (
        <polyline data-stair-path points={[...stairPath, ...(stairCursor ? [stairCursor] : [])].map((p) => svgPoint(p).join(',')).join(' ')}
          fill="none" stroke="#d2a106" strokeWidth={80} strokeDasharray="200 120" style={{ pointerEvents: 'none' }} />
      )}
      {tool === 'add-wall' && draft.a && (() => {
        const [x, y] = svgPoint(draft.a)
        return <circle cx={x} cy={y} r={120} fill="#42be65" style={{ pointerEvents: 'none' }} />
      })()}
    </ReviewCanvas>
    </>
  )
}

const DEFAULT_FLOOR_TO_FLOOR_MM = 4000
const REVIEW_TOOLS: [Tool, string, string][] = [['select', 'Pilih', 'V'], ['guide-line', 'Garis bantu', 'L'], ['add-wall', 'Dinding baru', 'W'], ['add-door', 'Pintu', 'D'], ['add-stair', 'Tangga', 'S'], ['assist', 'Perbaiki area', 'A']]
