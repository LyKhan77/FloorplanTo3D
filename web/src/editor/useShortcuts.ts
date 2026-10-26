import { useEffect } from 'react'
import type { Template } from '../api/types'
import { keyAction } from './lib/keys'
import { deleteOps, duplicateOps, rotateOps, templateOf } from './lib/transform'
import { useEditorStore } from './store'

const TYPING = 'input, textarea, select, [contenteditable=""], [contenteditable="true"]'

/** PRD/07 §10 shortcuts while the Editor tab is shown; typing in fields and open Carbon modals are left alone. */
export function useShortcuts(templates: Template[], save: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as Element | null
      if (target?.closest?.(TYPING) || document.querySelector('.cds--modal.is-visible')) return
      const action = keyAction(e)
      if (!action) return
      if (['save', 'undo', 'redo', 'duplicate'].includes(action)) e.preventDefault()
      const s = useEditorStore.getState()
      const picked = (s.view?.objects ?? []).filter((o) => s.selection.includes(o.id))
      const lockedNotice = () => { if (picked.some((o) => o.locked)) s.setNotice({ kind: 'warning', text: 'Objek terkunci' }) }
      const [kind, arg] = action.split(':')
      switch (kind) {
        case 'mode': return s.setMode(arg as 'orbit' | 'top' | 'walk')
        case 'tool': return s.setTool(arg as 'select' | 'distance' | 'area' | 'height')
        case 'snap': return s.setSnap(!s.snap)
        case 'undo': return s.undo()
        case 'redo': return s.redo()
        case 'save': return save()
        case 'cancel':
          if (s.mode === 'walk') s.setMode('orbit')
          else if (s.tool !== 'select') s.setTool('select')
          else s.select([])
          return
        case 'rotate':
          lockedNotice()
          if (picked.length) s.applyMany(rotateOps(picked, arg === '+90' ? 90 : -90))
          return
        case 'delete':
          lockedNotice()
          if (picked.length) s.applyMany(deleteOps(picked))
          return
        case 'duplicate': {
          lockedNotice()
          const ops = duplicateOps(picked, (picked[0] && templateOf(picked[0], templates)?.snap?.grid_mm) || 600)
          if (ops.length && s.applyMany(ops)) {
            const objs = useEditorStore.getState().view?.objects ?? []
            s.select(objs.slice(-ops.length).map((o) => o.id))
          }
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [templates, save])
}
