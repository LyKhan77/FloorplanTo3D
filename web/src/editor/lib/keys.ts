/** Keyboard map of PRD/07 §10. */
export type Action =
  | 'mode:orbit' | 'mode:top' | 'mode:walk' | 'tool:select' | 'tool:distance' | 'tool:area' | 'tool:height'
  | 'snap:toggle' | 'rotate:+90' | 'rotate:-90' | 'duplicate' | 'delete' | 'undo' | 'redo' | 'save' | 'cancel'

const PLAIN: Record<string, Action> = {
  '1': 'mode:orbit', '2': 'mode:top', '3': 'mode:walk', v: 'tool:select', m: 'tool:distance', a: 'tool:area',
  h: 'tool:height', g: 'snap:toggle',
}

export function keyAction(e: { key: string; shiftKey: boolean; ctrlKey: boolean; metaKey: boolean }): Action | null {
  const key = e.key.length === 1 ? e.key.toLowerCase() : e.key
  if (e.ctrlKey || e.metaKey) {
    if (key === 'z') return e.shiftKey ? 'redo' : 'undo'
    if (key === 'd') return 'duplicate'
    if (key === 's') return 'save'
    return null
  }
  if (key === 'Escape') return 'cancel'
  // Mac keyboards label Backspace "delete"
  if (key === 'Delete' || key === 'Backspace') return 'delete'
  if (key === 'r') return e.shiftKey ? 'rotate:-90' : 'rotate:+90'
  return e.shiftKey ? null : PLAIN[key] ?? null
}
