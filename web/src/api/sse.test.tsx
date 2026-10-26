import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { useProjectEvents } from './sse'

// jsdom has no EventSource; this fake records each connection so the test can drive it.
class FakeSource {
  static CLOSED = 2
  static all: FakeSource[] = []
  readyState = 1
  listeners: Record<string, (m: MessageEvent) => void> = {}
  onerror: (() => void) | null = null
  url: string
  constructor(url: string) {
    this.url = url
    FakeSource.all.push(this)
  }
  addEventListener(t: string, f: (m: MessageEvent) => void) { this.listeners[t] = f }
  close() { this.readyState = 2 }
  emit(seq: number) { this.listeners['stage.log']({ data: JSON.stringify({ seq, type: 'stage.log' }) } as MessageEvent) }
}

beforeEach(() => {
  FakeSource.all = []
  vi.useFakeTimers()
  vi.stubGlobal('EventSource', FakeSource)
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
)

test('reconnects from the last seq after the browser gives up (proxy 502 while the server restarts)', () => {
  const seen: number[] = []
  renderHook(() => useProjectEvents('p1', (e) => seen.push(e.seq)), { wrapper })
  const first = FakeSource.all[0]
  expect(first.url).toBe('/api/projects/p1/events?since=0')
  first.emit(5)
  first.readyState = FakeSource.CLOSED // a non-200 reply closes EventSource for good
  act(() => first.onerror?.())
  act(() => { vi.advanceTimersByTime(5000) })
  expect(FakeSource.all).toHaveLength(2)
  expect(FakeSource.all[1].url).toBe('/api/projects/p1/events?since=5')
  expect(seen).toEqual([5])
})

test('spec.created refreshes the project header (HEAD version) as well as the version list', () => {
  const qc = new QueryClient()
  const spy = vi.spyOn(qc, 'invalidateQueries')
  renderHook(() => useProjectEvents('p1', () => {}), {
    wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>,
  })
  FakeSource.all[0].listeners['spec.created']({ data: JSON.stringify({ seq: 1, type: 'spec.created' }) } as MessageEvent)
  const keys = spy.mock.calls.map(([f]) => f?.queryKey)
  expect(keys).toContainEqual(['specs', 'p1'])
  expect(keys).toContainEqual(['project', 'p1'])
})
