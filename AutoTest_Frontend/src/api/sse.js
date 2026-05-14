/**
 * Lightweight SSE client for POST requests.
 *
 * The native EventSource API only supports GET, but our agent streaming
 * endpoint is POST-based.  This helper uses `fetch` + `ReadableStream`
 * to parse the `text/event-stream` format and invoke callbacks.
 */

/**
 * @param {string} url        Absolute URL of the SSE endpoint.
 * @param {object} body       JSON-serializable request body.
 * @param {object} callbacks
 * @param {function} callbacks.onEvent  Called with each parsed data object.
 * @param {function} [callbacks.onError]  Called on network / parse errors.
 * @param {function} [callbacks.onDone]   Called when the stream closes.
 * @returns {{ abort: () => void }}       Handle to cancel the stream.
 */
export function postSSE(url, body, { onEvent, onError, onDone } = {}) {
  const controller = new AbortController()

  ;(async () => {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!response.ok) {
        const text = await response.text().catch(() => '')
        onError?.(new Error(`SSE request failed: ${response.status} ${text}`))
        onDone?.()
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // SSE frames are separated by double newlines
        const frames = buffer.split('\n\n')
        // Keep the last incomplete frame in the buffer
        buffer = frames.pop() || ''

        for (const frame of frames) {
          const trimmed = frame.trim()
          if (!trimmed) continue

          // Extract the data payload (supports multi-line data fields)
          const lines = trimmed.split('\n')
          let data = ''
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              data += line.slice(6)
            } else if (line.startsWith('data:')) {
              data += line.slice(5)
            }
          }

          if (!data) continue

          try {
            const parsed = JSON.parse(data)
            onEvent?.(parsed)
          } catch {
            // Non-JSON data line — skip
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        onError?.(err)
      }
    } finally {
      onDone?.()
    }
  })()

  return { abort: () => controller.abort() }
}
