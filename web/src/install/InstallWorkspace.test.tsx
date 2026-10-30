import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import gtJson from '../../../benchmarks/gatsu/gt_spec.json'
import { ApiError } from '../api/client'
import { useEditorStore } from '../editor/store'
import type { Spec } from '../types/spec'
import type { Installation } from '../types/installation'
import * as installApi from './api'
import { InstallWorkspace } from './InstallWorkspace'
import { useInstallStore } from './store'

vi.mock('./api', async (orig) => ({ ...(await orig<typeof import('./api')>()), snapTray: vi.fn(), snapBox: vi.fn(), snapBoxes: vi.fn() }))
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

  it('Shift-drag traces a row with one request', async () => {
    vi.mocked(installApi.snapBoxes).mockResolvedValue([box(2300, 4400), box(2920, 4400), box(3540, 4400)])
    const { svg } = setup()
    fireEvent.keyDown(window, { key: 'k' })
    fireEvent.pointerDown(svg, { clientX: 1500, clientY: -5500, button: 0, shiftKey: true })
    fireEvent.pointerMove(svg, { clientX: 4500, clientY: -3500, button: 0, shiftKey: true })
    fireEvent.pointerUp(svg, { clientX: 4500, clientY: -3500, button: 0, shiftKey: true })
    await waitFor(() => expect(ist().view!.objects).toHaveLength(3))
    expect(vi.mocked(installApi.snapBoxes)).toHaveBeenCalledTimes(1)
    expect(vi.mocked(installApi.snapBox)).not.toHaveBeenCalled()
  })
})

