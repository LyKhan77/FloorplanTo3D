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
  openings: [], stairs: [], objects: [], explanation: 'Dinding nyasar.', notes: [], issues: [], valid,
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

  it('Terima adds every add_object of a filled room', async () => {
    const add = (x: number) => ({ op: 'add_object', template_id: 'rack-42u-600x1200', template_version: '1.1.0',
      position: [x, 3000, 0], rotation: 0, dims: [600, 1200, 2000] })
    script = [{ event: 'session', session_id: 's1' }, { ...proposal(), ops: [add(2000), add(2600)] } as AssistEvent,
      { event: 'done' }]
    render(<AssistPanel projectId="p1" />)
    await send('isi ruang')
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Terima' })) })
    expect(st().ops.map((o) => o.op)).toEqual(['add_object', 'add_object'])
  })

  it('an invalid proposal keeps Terima disabled', async () => {
    script = [{ event: 'session', session_id: 's1' }, proposal(false), { event: 'done' }]
    render(<AssistPanel projectId="p1" />)
    await send('hapus')
    expect((screen.getByRole('button', { name: 'Terima' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/Terima nonaktif/)).toBeTruthy()
  })
})

describe('drawn boxes', () => {
  it('pointing at the same box twice keeps one K', () => {
    const s = useAssistStore.getState()
    s.close()
    const box = { center: [1000, 2000] as [number, number], size: [800, 1200] as [number, number], rotation: 0 as const }
    expect(s.addDrawn(box)).toBe('K1')
    expect(useAssistStore.getState().addDrawn({ ...box, center: [1010, 1995] })).toBe('K1')
    expect(useAssistStore.getState().drawn).toHaveLength(1)
  })
})

describe('AssistPanel in Instalasi & Interior', () => {
  it('Terima adds the ops to the installation, not the layout', async () => {
    const { useInstallStore } = await import('../../install/store')
    const inst = { schema_version: '1.0', meta: { version: 4, layout_version: 1, default_mounting: 'overhead', id_seq: {} },
      cable_trays: [], objects: [], provenance_log: [] }
    useInstallStore.getState().load(inst as never, 'p1')
    st().load('p1', gt)
    useAssistStore.getState().close()
    useAssistStore.getState().setLayer('installation')
    useAssistStore.getState().open([0, 0, 5000, 5000])
    const add = { op: 'add_object', template_id: 'rack-42u-600x1200', template_version: '1.1.0', position: [2000, 3000, 0],
      rotation: 0, dims: [600, 1200, 2000] }
    script = [{ event: 'session', session_id: 's1' }, { ...proposal(), ops: [add] } as AssistEvent, { event: 'done' }]
    render(<AssistPanel projectId="p1" />)
    await send('isi')
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Terima' })) })
    expect(useInstallStore.getState().ops).toHaveLength(1)
    expect(st().ops).toEqual([])
    useAssistStore.getState().setLayer('layout')
  })
})
