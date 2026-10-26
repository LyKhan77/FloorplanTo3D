import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import type { ApiEvent } from './types'

export const EVENT_TYPES = ['run.queued', 'run.started', 'run.finished', 'stage.started', 'stage.finished',
  'stage.progress', 'stage.log', 'stage.artifact', 'llm.decision', 'spec.created', 'output.ready']

/** One SSE connection per project page. The browser reconnects by itself and sends Last-Event-ID. */
export function useProjectEvents(id: string | undefined, onEvent: (e: ApiEvent) => void) {
  const qc = useQueryClient()
  const handler = useRef(onEvent)
  useEffect(() => {
    handler.current = onEvent
  })
  useEffect(() => {
    if (!id) return
    const source = new EventSource(`/api/projects/${id}/events?since=0`)
    const listener = (msg: MessageEvent) => {
      const e = JSON.parse(msg.data) as ApiEvent
      handler.current(e)
      if (e.type.startsWith('run.') || e.type === 'stage.finished') {
        qc.invalidateQueries({ queryKey: ['project', id] })
        qc.invalidateQueries({ queryKey: ['runs', id] })
      }
      if (e.type === 'spec.created') qc.invalidateQueries({ queryKey: ['specs', id] })
      if (e.type === 'output.ready') qc.invalidateQueries({ queryKey: ['outputs', id] })
    }
    for (const t of EVENT_TYPES) source.addEventListener(t, listener as EventListener)
    return () => source.close()
  }, [id, qc])
}
