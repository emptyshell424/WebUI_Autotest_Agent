import { describe, it, expect, vi, beforeEach } from 'vitest'
import { postSSE } from './sse.js'

/**
 * Create a fake ReadableStream that yields the given chunks one at a time.
 */
function fakeReadableStream(chunks) {
  let idx = 0
  const encoder = new TextEncoder()
  return {
    getReader() {
      return {
        read() {
          if (idx < chunks.length) {
            return Promise.resolve({ value: encoder.encode(chunks[idx++]), done: false })
          }
          return Promise.resolve({ value: undefined, done: true })
        },
      }
    },
  }
}

describe('postSSE', () => {
  let originalFetch

  beforeEach(() => {
    originalFetch = globalThis.fetch
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('parses SSE data frames and calls onEvent', async () => {
    const events = []
    const sseData =
      'data: {"event_type":"thinking","step":1,"data":{"thought":"hi"},"timestamp":1}\n\n' +
      'data: {"event_type":"action","step":1,"data":{"tool":"T"},"timestamp":2}\n\n'

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: fakeReadableStream([sseData]),
    })

    const done = new Promise((resolve) => {
      postSSE('http://localhost/test', { prompt: 'hello' }, {
        onEvent: (e) => events.push(e),
        onDone: resolve,
      })
    })

    await done
    expect(events).toHaveLength(2)
    expect(events[0].event_type).toBe('thinking')
    expect(events[1].event_type).toBe('action')
  })

  it('calls onError for non-ok responses', async () => {
    let error = null
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve('Internal Server Error'),
    })

    const done = new Promise((resolve) => {
      postSSE('http://localhost/test', {}, {
        onError: (e) => { error = e },
        onDone: resolve,
      })
    })

    await done
    expect(error).not.toBeNull()
    expect(error.message).toContain('500')
  })

  it('handles chunked data across multiple reads', async () => {
    const events = []
    // Split a single SSE frame across two chunks
    const chunk1 = 'data: {"event_type":"think'
    const chunk2 = 'ing","step":1,"data":{},"timestamp":1}\n\n'

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: fakeReadableStream([chunk1, chunk2]),
    })

    const done = new Promise((resolve) => {
      postSSE('http://localhost/test', {}, {
        onEvent: (e) => events.push(e),
        onDone: resolve,
      })
    })

    await done
    expect(events).toHaveLength(1)
    expect(events[0].event_type).toBe('thinking')
  })

  it('abort cancels the fetch', () => {
    globalThis.fetch = vi.fn().mockReturnValue(new Promise(() => {}))
    const handle = postSSE('http://localhost/test', {}, {})
    expect(typeof handle.abort).toBe('function')
    // Should not throw
    handle.abort()
  })

  it('skips non-JSON data lines', async () => {
    const events = []
    const sseData =
      'data: not json\n\n' +
      'data: {"event_type":"finish","step":5,"data":{},"timestamp":3}\n\n'

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: fakeReadableStream([sseData]),
    })

    const done = new Promise((resolve) => {
      postSSE('http://localhost/test', {}, {
        onEvent: (e) => events.push(e),
        onDone: resolve,
      })
    })

    await done
    expect(events).toHaveLength(1)
    expect(events[0].event_type).toBe('finish')
  })

  it('sends POST with correct headers and body', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: fakeReadableStream([]),
    })

    const done = new Promise((resolve) => {
      postSSE('http://localhost/api', { prompt: 'test', max_steps: 10 }, {
        onDone: resolve,
      })
    })

    await done
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    const [url, opts] = globalThis.fetch.mock.calls[0]
    expect(url).toBe('http://localhost/api')
    expect(opts.method).toBe('POST')
    expect(opts.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(opts.body)).toEqual({ prompt: 'test', max_steps: 10 })
  })
})
