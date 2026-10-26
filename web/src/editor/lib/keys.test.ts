import { describe, expect, it } from 'vitest'
import { keyAction } from './keys'

const k = (key: string, mods: Partial<{ shiftKey: boolean; ctrlKey: boolean; metaKey: boolean }> = {}) =>
  keyAction({ key, shiftKey: false, ctrlKey: false, metaKey: false, ...mods })

describe('keyAction', () => {
  it('maps every shortcut of PRD 07 §10', () => {
    expect([k('1'), k('2'), k('3')]).toEqual(['mode:orbit', 'mode:top', 'mode:walk'])
    expect([k('v'), k('m'), k('a'), k('h'), k('g')]).toEqual(['tool:select', 'tool:distance', 'tool:area', 'tool:height', 'snap:toggle'])
    expect(k('V', { shiftKey: false })).toBe('tool:select')
    expect(k('r')).toBe('rotate:+90')
    expect(k('R', { shiftKey: true })).toBe('rotate:-90')
    expect(k('d', { ctrlKey: true })).toBe('duplicate')
    expect(k('d', { metaKey: true })).toBe('duplicate')
    expect(k('Delete')).toBe('delete')
    expect(k('Backspace')).toBe('delete')
    expect(k('z', { ctrlKey: true })).toBe('undo')
    expect(k('Z', { metaKey: true, shiftKey: true })).toBe('redo')
    expect(k('s', { ctrlKey: true })).toBe('save')
    expect(k('Escape')).toBe('cancel')
  })

  it('ignores plain letters with ctrl except the mapped ones', () => {
    expect(k('r', { ctrlKey: true })).toBeNull()
    expect(k('a', { metaKey: true })).toBeNull()
    expect(k('v', { ctrlKey: true })).toBeNull()
    expect(k('x')).toBeNull()
    expect(k('d')).toBeNull()
    expect(k('s')).toBeNull()
    expect(k('1', { ctrlKey: true })).toBeNull()
  })
})
