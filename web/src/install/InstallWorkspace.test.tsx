import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, createEvent, fireEvent, render, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import gtJson from '../../../benchmarks/gatsu/gt_spec.json'
import { ApiError } from '../api/client'
import { useEditorStore } from '../editor/store'
import type { Spec } from '../types/spec'
import type { Installation } from '../types/installation'
import * as installApi from './api'
import { InstallWorkspace } from './InstallWorkspace'
import { useInstallStore } from './store'

vi.mock('./api', async (orig) => ({ ...(await orig<typeof import('./api')>()), snapTray: vi.fn(), snapBox: vi.fn(), fitBox: vi.fn() }))
vi.mock('../api/hooks', async (orig) => ({ ...(await orig<typeof import('../api/hooks')>()),
  useTemplates: () => ({ data: [{ id: 'rack-42u-600x1200', version: '1.0.0', category: 'rack', dims: { w: 600, d: 1200, h: 2000 } }] }) }))

const gt = gtJson as unknown as Spec
const base = { schema_version: '1.0', meta: { version: 1, layout_version: 1, default_mounting: 'overhead', id_seq: {} },
  cable_trays: [], objects: [], provenance_log: [] } as unknown as Installation
const ist = () => useInstallStore.getState()

function setup() {
  const r = render(<QueryClientProvider client={new QueryClient()}><InstallWorkspace projectId="p1" backdrop={null} drops={[]} /></QueryClientProvider>)
  const svg = r.container.querySelector('svg.review-canvas')!
  const click = (x: number, y: number, extra: object = {}) => {
    fireEvent.pointerDown(svg, { clientX: x, clientY: -y, button: 0, ...extra })
    fireEvent.pointerUp(svg, { clientX: x, clientY: -y, button: 0, ...extra })
  }
  return { ...r, svg, click }
}

describe('InstallWorkspace', () => {
  beforeEach(() => {
    useEditorStore.getState().load('p1', gt)
    ist().load(base)
    vi.mocked(installApi.snapTray).mockReset()
    vi.mocked(installApi.snapBox).mockReset()
  })

  it('T, three clicks and Enter trace a tray snapped to the drawing', async () => {
    vi.mocked(installApi.snapTray).mockResolvedValue({ path: [[24000, 395], [30000, 395], [30000, -3000]], width: 200 })
    const { click } = setup()
    fireEvent.keyDown(window, { key: 't' })
    click(24000, 500); click(30000, 300); click(30000, -3000)
    act(() => { fireEvent.keyDown(window, { key: 'Enter' }) })
    await waitFor(() => expect(ist().view!.cable_trays).toHaveLength(1))
    expect(vi.mocked(installApi.snapTray).mock.calls[0][1]).toEqual([[24000, 500], [30000, 300], [30000, -3000]])
    expect(ist().view!.cable_trays![0]).toMatchObject({ id: 'T1', tray_class: 'data', width: 200, path: [[24000, 395], [30000, 395], [30000, -3000]] })
  })

  it('keeps the drawn path when there is nothing to snap to (Review Focus 1)', async () => {
    vi.mocked(installApi.snapTray).mockRejectedValue(new ApiError(404, 'no_run', 'no run'))
    const { click } = setup()
    fireEvent.keyDown(window, { key: 't' })
    click(1000, 1000); click(4000, 1000)
    act(() => { fireEvent.keyDown(window, { key: 'Enter' }) })
    await waitFor(() => expect(ist().view!.cable_trays).toHaveLength(1))
    expect(ist().view!.cable_trays![0].path).toEqual([[1000, 1000], [4000, 1000]])
  })

  it('K and a click place the rack the drawing shows', async () => {
    vi.mocked(installApi.snapBox).mockResolvedValue({ center: [2300, 4400], size: [600, 1200], rotation: 0,
      template_id: 'rack-42u-600x1200', template_version: '1.0.0', dims: [600, 1200, 2000] })
    const { click } = setup()
    fireEvent.keyDown(window, { key: 'k' })
    click(2300, 4400)
    await waitFor(() => expect(ist().view!.objects).toHaveLength(1))
    expect(ist().view!.objects![0]).toMatchObject({ template_id: 'rack-42u-600x1200', position: [2300, 4400, 0], rotation: 0, dims: [600, 1200, 2000] })
  })

  it('the layout is read-only: a click on a wall selects nothing', () => {
    const { container } = setup()
    fireEvent.click(container.querySelector('line[data-wall]')!)
    expect(useEditorStore.getState().selection).toEqual([])
  })
})

describe('InstallWorkspace racks (review I3, I8)', () => {
  beforeEach(() => {
    useEditorStore.getState().load('p1', gt)
    ist().load(base)
  })
  const box = (x: number, y: number) => ({ center: [x, y] as [number, number], size: [600, 1200] as [number, number], rotation: 0,
    template_id: 'rack-42u-600x1200', template_version: '1.0.0', dims: [600, 1200, 2000] as [number, number, number] })

  it('a second click on the same box adds no second rack', async () => {
    vi.mocked(installApi.snapBox).mockResolvedValue(box(2300, 4400))
    const { click } = setup()
    fireEvent.keyDown(window, { key: 'k' })
    click(2300, 4400)
    await waitFor(() => expect(ist().view!.objects).toHaveLength(1))
    click(2310, 4390)
    await waitFor(() => expect(ist().notice?.text).toMatch(/sudah ada/))
    expect(ist().view!.objects).toHaveLength(1)
  })

  it('Shift-drag places one rack on the dragged box, its sides fitted to the drawing (no auto row)', async () => {
    vi.mocked(installApi.fitBox).mockResolvedValue(box(3000, 4500))
    const { svg } = setup()
    fireEvent.keyDown(window, { key: 'k' })
    fireEvent.pointerDown(svg, { clientX: 2650, clientY: -5150, button: 0, shiftKey: true })
    fireEvent.pointerMove(svg, { clientX: 3350, clientY: -3850, button: 0, shiftKey: true })
    fireEvent.pointerUp(svg, { clientX: 3350, clientY: -3850, button: 0, shiftKey: true })
    await waitFor(() => expect(ist().view!.objects).toHaveLength(1))
    expect(vi.mocked(installApi.fitBox).mock.calls[0].slice(1)).toEqual([[2650, 5150], [3350, 3850]])
    expect(ist().view!.objects![0]).toMatchObject({ position: [3000, 4500, 0] })
    expect(vi.mocked(installApi.snapBox)).not.toHaveBeenCalled()
  })
})


describe('InstallWorkspace device editing (fit-out, 2D)', () => {
  const rack = { id: 'RK1', template_id: 'rack-42u-600x1200', template_version: '1.1.0', position: [2000, 3000, 0], rotation: 0,
    dims: [600, 1200, 2000], room_id: null, label: null, locked: false }
  beforeEach(() => {
    useEditorStore.getState().load('p1', gt)
    ist().load({ ...base, objects: [rack] } as unknown as Installation)
    ist().setTool('select')
  })

  it('a Library card dropped on the canvas adds the device there', () => {
    const { container } = setup()
    useEditorStore.getState().setDragging({ id: 'ups-cabinet-generic', version: '1.1.0', name: 'UPS', category: 'power',
      dims: { w: 1200, d: 800, h: 2000 }, thumbnail_url: '', asset_url: '' })
    const zone = container.querySelector('[data-drop-zone]')!
    // jsdom's drop event carries no mouse position: set it on the event
    const ev = createEvent.drop(zone, { dataTransfer: { getData: () => 'ups-cabinet-generic@1.1.0' } })
    Object.defineProperties(ev, { clientX: { value: 3000 }, clientY: { value: -4000 } })
    fireEvent(zone, ev)
    expect(ist().ops.at(-1)).toMatchObject({ op: 'add_object', template_id: 'ups-cabinet-generic', position: [3000, 4000, 0],
      dims: [1200, 800, 2000] })
  })

  it('dragging a selected device moves it', () => {
    const { svg } = setup()
    ist().select(['RK1'])
    fireEvent.pointerDown(svg, { clientX: 2000, clientY: -3000, button: 0 })
    fireEvent.pointerMove(svg, { clientX: 2500, clientY: -3000, button: 0 })
    fireEvent.pointerUp(svg, { clientX: 2500, clientY: -3000, button: 0 })
    expect(ist().ops.at(-1)).toMatchObject({ op: 'update_object', id: 'RK1', position: [2500, 3000, 0] })
  })

  it('R turns the selected device a quarter', () => {
    setup()
    ist().select(['RK1'])
    fireEvent.keyDown(window, { key: 'r' })
    expect(ist().ops.at(-1)).toMatchObject({ op: 'update_object', id: 'RK1', rotation: 90 })
  })
})

describe('InstallWorkspace device ops the server accepts', () => {
  it('a move and a turn carry the reason the server asks for (review C1)', () => {
    const rack = { id: 'RK1', template_id: 'rack-42u-600x1200', template_version: '1.1.0', position: [2000, 3000, 0], rotation: 0,
      dims: [600, 1200, 2000], room_id: null, label: null, locked: false }
    useEditorStore.getState().load('p1', gt)
    ist().load({ ...base, objects: [rack] } as unknown as Installation)
    ist().setTool('select')
    const { svg } = setup()
    ist().select(['RK1'])
    fireEvent.pointerDown(svg, { clientX: 2000, clientY: -3000, button: 0 })
    fireEvent.pointerMove(svg, { clientX: 2500, clientY: -3000, button: 0 })
    fireEvent.pointerUp(svg, { clientX: 2500, clientY: -3000, button: 0 })
    fireEvent.keyDown(window, { key: 'r' })
    expect(ist().ops.map((o) => (o as { reason?: string }).reason)).toEqual(['dipindah di editor', 'diputar di editor'])
  })

  it('leaving the installation canvas with tool A open ends the equipment chat (review: Terima to the wrong store)', async () => {
    const { useAssistStore } = await import('../editor/assist/store')
    ist().load(base)
    ist().setTool('assist')
    const r = setup()
    expect(useAssistStore.getState().layer).toBe('installation')
    r.unmount()
    expect(useAssistStore.getState().layer).toBe('layout')
  })
})

describe('InstallLayer front marks', () => {
  const dev = (id: string, rotation: number) => ({ id, template_id: 'rack-42u-600x1200', template_version: '1.1.0',
    position: [2000, 3000, 0], rotation, dims: [600, 1200, 2000], room_id: null, label: null, locked: false })
  const mid = (el: Element) => {
    const [x1, y1, x2, y2] = ['x1', 'y1', 'x2', 'y2'].map((k) => Number(el.getAttribute(k)))
    return [(x1 + x2) / 2, -(y1 + y2) / 2]  // back to plan mm (svg y is flipped)
  }

  it('marks the front edge of each device, turning with it', () => {
    ist().load({ ...base, objects: [dev('RK1', 0), dev('RK2', 90)] } as unknown as Installation)
    const { container } = setup()
    const [a, b] = ['RK1', 'RK2'].map((id) => container.querySelector(`[data-front="${id}"]`)!)
    expect(mid(a)[0]).toBeCloseTo(2000, 0)
    expect(mid(a)[1]).toBeCloseTo(3600, 0)  // rotation 0 faces +y: front edge at y + d/2
    expect(mid(b)[0]).toBeCloseTo(1400, 0)  // rotation 90 faces -x: front edge at x - d/2
    expect(mid(b)[1]).toBeCloseTo(3000, 0)
  })
})
