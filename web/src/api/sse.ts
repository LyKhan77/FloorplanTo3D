import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import type { ApiEvent } from './types'

export const EVENT_TYPES = ['run.queued', 'run.started', 'run.finished', 'stage.started', 'stage.finished',
  'stage.progress', 'stage.log', 'stage.artifact', 'llm.decision', 'spec.created', 'output.ready']

/** One SSE connection per project page. The browser reconnects by itself after network errors, but a non-200
 * reply (a proxy's 502 while the server restarts) closes EventSource for good, so reopen it from the last seq. */
export function useProjectEvents(id: string | undefined, onEvent: (e: ApiEvent) => void) {
  const qc = useQueryClient()
  const handler = useRef(onEvent)
  useEffect(() => {
    handler.current = onEvent
  })
  useEffect(() => {
    if (!id) return
    let source: EventSource
    let last = 0
    let retry: ReturnType<typeof setTimeout> | undefined
    let delay = 1000
    const listener = (msg: MessageEvent) => {
      const e = JSON.parse(msg.data) as ApiEvent
      last = e.seq
      delay = 1000
      handler.current(e)
      if (e.type.startsWith('run.') || e.type === 'stage.finished') {
        qc.invalidateQueries({ queryKey: ['project', id] })
        qc.invalidateQueries({ queryKey: ['runs', id] })
      }
      if (e.type === 'spec.created') {
        qc.invalidateQueries({ queryKey: ['specs', id] })
        qc.invalidateQueries({ queryKey: ['project', id] })
        qc.invalidateQueries({ queryKey: ['spec', id] })
      }
      if (e.type === 'output.ready') qc.invalidateQueries({ queryKey: ['outputs', id] })
    }
    const connect = () => {
      source = new EventSource(`/api/projects/${id}/events?since=${last}`)
      for (const t of EVENT_TYPES) source.addEventListener(t, listener as EventListener)
      source.onerror = () => {
        if (source.readyState !== EventSource.CLOSED) return
        retry = setTimeout(connect, delay)
        delay = Math.min(delay * 2, 10000)
      }
    }
    connect()
    return () => {
      clearTimeout(retry)
      source.close()
    }
  }, [id, qc])
}
