import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import gtJson from '../../../../benchmarks/gatsu/gt_spec.json'
import type { Spec } from '../../types/spec'
import { useEditorStore } from '../store'
import { AssistPanel } from './AssistPanel'
import { useAssistStore } from './store'
import type { AssistEvent } from './stream'

const gt = gtJson as unknown as Spec
const st = () => useEditorStore.getState()
let script: AssistEvent[] = []
const decisions: boolean[] = []

vi.mock('./stream', () => ({
  streamAssist: vi.fn(async (_pid: string, _body: unknown, on: (e: AssistEvent) => void) => { for (const e of script) on(e) }),
  postDecision: vi.fn(async (_pid: string, _sid: string, accepted: boolean) => { decisions.push(accepted) }),
}))

const wall = gt.walls![5].id
const proposal = (valid = true): AssistEvent => ({
  event: 'proposal', ops: [{ op: 'delete_wall', id: wall, reason: 'asisten: hapus' }], deleted: [wall], added: [], moved: [],
  openings: [], explanation: 'Dinding nyasar.', notes: [], issues: [], valid,
})

async function send(text: string) {
  fireEvent.change(screen.getByRole('textbox'), { target: { value: text } })
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Kirim' })) })
}

describe('AssistPanel', () => {
  beforeEach(() => {
    st().load('p1', gt)
    st().setTool('assist')
    useAssistStore.getState().close()  // the store outlives a render: start every test with a fresh chat
    useAssistStore.getState().open([0, 0, 5000, 5000])
    decisions.length = 0
  })

  it('shows the message, the streamed steps and the question', async () => {
    script = [{ event: 'session', session_id: 's1' }, { event: 'step', text: 'Membaca 3 dinding…' },
      { event: 'question', text: 'Dinding mana?' }, { event: 'done' }]
    render(<AssistPanel projectId="p1" />)
    await send('hapus ini')
    expect(screen.getByText('hapus ini')).toBeTruthy()
    expect(screen.getByText(/Membaca 3 dinding/)).toBeTruthy()
    expect(screen.getByText('Dinding mana?')).toBeTruthy()
  })

  it('Terima adds the proposal ops to the pending edits', async () => {
    script = [{ event: 'session', session_id: 's1' }, proposal(), { event: 'done' }]
    render(<AssistPanel projectId="p1" />)
    await send('hapus')
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Terima' })) })
    expect(st().ops).toEqual([{ op: 'delete_wall', id: wall, reason: 'asisten: hapus' }])
    expect(decisions).toEqual([true])
    expect(useAssistStore.getState().proposal).toBeNull()
  })

  it('Tolak leaves the edits unchanged', async () => {
    script = [{ event: 'session', session_id: 's1' }, proposal(), { event: 'done' }]
    render(<AssistPanel projectId="p1" />)
    await send('hapus')
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Tolak' })) })
    expect(st().ops).toEqual([])
    expect(decisions).toEqual([false])
  })

  it('a manual edit after the proposal makes it stale', async () => {
    script = [{ event: 'session', session_id: 's1' }, proposal(), { event: 'done' }]
    render(<AssistPanel projectId="p1" />)
    await send('hapus')
    act(() => { st().apply({ op: 'delete_wall', id: gt.walls![0].id, reason: 'manual' }) })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Terima' })) })
    expect(st().ops).toHaveLength(1)
    expect(screen.getByText(/usulan usang, kirim ulang/i)).toBeTruthy()
  })

  it('a message while a proposal is open revises it, it does not reject it', async () => {
    script = [{ event: 'session', session_id: 's1' }, proposal(), { event: 'done' }]
    render(<AssistPanel projectId="p1" />)
    await send('hapus')
    await send('jangan yang itu, yang sebelah')
    expect(screen.getByText(/direvisi/)).toBeTruthy()
    expect(screen.queryAllByText(/ditolak/).map((e) => e.textContent)).toEqual([])
    expect(decisions).toEqual([])
  })

  it('an invalid proposal keeps Terima disabled', async () => {
    script = [{ event: 'session', session_id: 's1' }, proposal(false), { event: 'done' }]
    render(<AssistPanel projectId="p1" />)
    await send('hapus')
    expect((screen.getByRole('button', { name: 'Terima' }) as HTMLButtonElement).disabled).toBe(true)
  })
})
