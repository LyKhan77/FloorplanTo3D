import { afterEach, describe, expect, it, vi } from 'vitest'
import { streamAssist, type AssistEvent } from './stream'

function body(chunks: string[]): Response {
  const enc = new TextEncoder()
  const stream = new ReadableStream({
    start(c) { for (const ch of chunks) c.enqueue(enc.encode(ch)); c.close() },
  })
  return new Response(stream, { status: 200, headers: { 'content-type': 'text/event-stream' } })
}

describe('streamAssist', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('parses events split across chunks, in order', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => body([
      'event: session\ndata: {"session_id": "s1"}\n\nevent: st',
      'ep\ndata: {"text": "Menunggu Strata…"}\n',
      '\nevent: done\ndata: {}\n\n',
    ])))
    const got: AssistEvent[] = []
    await streamAssist('p1', { base_version: 1, ops: [], box: [0, 0, 1, 1], selection: [], message: 'x' }, (e) => got.push(e))
    expect(got).toEqual([{ event: 'session', session_id: 's1' }, { event: 'step', text: 'Menunggu Strata…' }, { event: 'done' }])
  })

  it('an HTTP error throws the API error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: { code: 'no_session', message: 'sesi hilang' } }), { status: 404 })))
    await expect(streamAssist('p1', { base_version: 1, ops: [], box: [0, 0, 1, 1], selection: [], message: 'x' }, () => {}))
      .rejects.toMatchObject({ status: 404, code: 'no_session' })
  })
})
