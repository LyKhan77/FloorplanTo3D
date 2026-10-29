import { useState } from 'react'
import type { Backdrop, ReviewTask } from '../../api/types'
import type { Room } from '../../types/spec'
import { useEditorStore } from '../store'
import { svgPoint } from './planTransform'
import { ReviewCanvas } from './ReviewCanvas'
import { closeGapOps, snapGuide } from './tools'

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
      const r = closeGapOps(task, true, s.view!)
      if (s.applyMany(r.ops) && r.doorSkipped) s.setNotice({ kind: 'info', text: 'Celah ditutup; pintu bisa ditambahkan setelah Simpan' })
    }
  }
  const onPointer = (kind: 'down' | 'move' | 'up', mm: Pt, e: React.PointerEvent) => {
    if (tool !== 'guide-line' || e.button > 0) return false
    if (kind === 'down') setRough({ a: mm, b: mm })
    else if (kind === 'move' && rough) setRough({ ...rough, b: mm })
    else if (kind === 'up' && rough) {
      setRough(null)
      if (Math.hypot(mm[0] - rough.a[0], mm[1] - rough.a[1]) > 300) void snapGuide(projectId, rough.a, mm)
    }
    return true
  }

  return (
    <ReviewCanvas rooms={rooms} tasks={tasks} backdrop={backdrop} onCanvasPointer={onPointer}>
      {tool === 'close-gap' && task?.kind === 'gap' && [task.fix.a, task.fix.b].map((p, i) => {
        if (!p) return null
        const [x, y] = svgPoint(p)
        return <circle key={i} data-handle={i} cx={x} cy={y} r={160} className={`review-handle${picked.includes(i) ? ' is-picked' : ''}`}
          onClick={(e) => { e.stopPropagation(); pickHandle(i) }} />
      })}
      {rough && (() => {
        const [a, b] = [svgPoint(rough.a), svgPoint(rough.b)]
        return <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#42be65" strokeWidth={80} strokeDasharray="200 120" />
      })()}
    </ReviewCanvas>
  )
}
