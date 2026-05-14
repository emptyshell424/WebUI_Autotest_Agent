import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAgentStore } from './agent.js'

// Mock the SSE module
vi.mock('../api/sse.js', () => ({
  postSSE: vi.fn(() => ({ abort: vi.fn() })),
}))

import { postSSE } from '../api/sse.js'

describe('agent store', () => {
  let store

  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    store = useAgentStore()
  })

  describe('initial state', () => {
    it('starts with empty events', () => {
      expect(store.events).toEqual([])
    })

    it('starts not running', () => {
      expect(store.running).toBe(false)
    })

    it('starts with no error', () => {
      expect(store.error).toBeNull()
    })

    it('starts with no runId', () => {
      expect(store.runId).toBeNull()
    })

    it('starts with no agentStatus', () => {
      expect(store.agentStatus).toBeNull()
    })
  })

  describe('getters', () => {
    it('hasEvents returns false when empty', () => {
      expect(store.hasEvents).toBe(false)
    })

    it('hasEvents returns true after adding events', () => {
      store.events = [{ event_type: 'thinking', step: 1, data: {}, timestamp: 1 }]
      expect(store.hasEvents).toBe(true)
    })

    it('taskAnalysis returns the correct event', () => {
      store.events = [
        { event_type: 'task_analysis', step: 0, data: { intent: 'test' }, timestamp: 1 },
        { event_type: 'thinking', step: 1, data: {}, timestamp: 2 },
      ]
      expect(store.taskAnalysis.data.intent).toBe('test')
    })

    it('taskAnalysis returns null if absent', () => {
      store.events = [{ event_type: 'thinking', step: 1, data: {}, timestamp: 1 }]
      expect(store.taskAnalysis).toBeNull()
    })

    it('plan returns the correct event', () => {
      store.events = [
        { event_type: 'plan', step: 0, data: { goal: 'login test' }, timestamp: 1 },
      ]
      expect(store.plan.data.goal).toBe('login test')
    })

    it('thinkingEvents filters correctly', () => {
      store.events = [
        { event_type: 'task_analysis', step: 0, data: {}, timestamp: 1 },
        { event_type: 'thinking', step: 1, data: {}, timestamp: 2 },
        { event_type: 'action', step: 1, data: {}, timestamp: 3 },
        { event_type: 'thinking', step: 2, data: {}, timestamp: 4 },
      ]
      expect(store.thinkingEvents).toHaveLength(2)
    })

    it('actionEvents filters correctly', () => {
      store.events = [
        { event_type: 'thinking', step: 1, data: {}, timestamp: 1 },
        { event_type: 'action', step: 1, data: { tool: 'search_knowledge' }, timestamp: 2 },
      ]
      expect(store.actionEvents).toHaveLength(1)
      expect(store.actionEvents[0].data.tool).toBe('search_knowledge')
    })

    it('planStepEvents filters correctly', () => {
      store.events = [
        { event_type: 'plan_step_complete', step: 2, data: { step_number: 1 }, timestamp: 1 },
        { event_type: 'thinking', step: 3, data: {}, timestamp: 2 },
      ]
      expect(store.planStepEvents).toHaveLength(1)
    })

    it('finishEvent returns the finish event', () => {
      store.events = [
        { event_type: 'finish', step: 5, data: { status: 'success' }, timestamp: 1 },
      ]
      expect(store.finishEvent.data.status).toBe('success')
    })

    it('errorEvents filters correctly', () => {
      store.events = [
        { event_type: 'error', step: 3, data: { error: 'boom' }, timestamp: 1 },
        { event_type: 'thinking', step: 4, data: {}, timestamp: 2 },
      ]
      expect(store.errorEvents).toHaveLength(1)
    })

    it('summary returns the summary event', () => {
      store.events = [
        { event_type: 'summary', run_id: 'r1', status: 'success', steps: 3, timestamp: 1 },
      ]
      expect(store.summary.run_id).toBe('r1')
    })

    it('stepPairs pairs thinking with action by step number', () => {
      store.events = [
        { event_type: 'thinking', step: 1, data: { thought: 'A' }, timestamp: 1 },
        { event_type: 'action', step: 1, data: { tool: 'T1' }, timestamp: 2 },
        { event_type: 'thinking', step: 2, data: { thought: 'B' }, timestamp: 3 },
      ]
      const pairs = store.stepPairs
      expect(pairs).toHaveLength(2)
      expect(pairs[0].thinking.data.thought).toBe('A')
      expect(pairs[0].action.data.tool).toBe('T1')
      expect(pairs[1].thinking.data.thought).toBe('B')
      expect(pairs[1].action).toBeNull()
    })
  })

  describe('startAgentRun', () => {
    it('sets running to true and clears state', () => {
      store.events = [{ event_type: 'thinking', step: 1 }]
      store.error = 'old error'
      store.runId = 'old-id'
      store.agentStatus = 'success'

      store.startAgentRun('test prompt')

      expect(store.running).toBe(true)
      expect(store.events).toEqual([])
      expect(store.error).toBeNull()
      expect(store.runId).toBeNull()
      expect(store.agentStatus).toBeNull()
    })

    it('calls postSSE with correct arguments', () => {
      store.startAgentRun('my prompt', 10)
      expect(postSSE).toHaveBeenCalledTimes(1)
      const [url, body] = postSSE.mock.calls[0]
      expect(url).toContain('/agent/run/stream')
      expect(body).toEqual({ prompt: 'my prompt', max_steps: 10 })
    })

    it('processes events via onEvent callback', () => {
      let capturedOnEvent
      postSSE.mockImplementation((_url, _body, { onEvent }) => {
        capturedOnEvent = onEvent
        return { abort: vi.fn() }
      })

      store.startAgentRun('test')
      capturedOnEvent({ event_type: 'thinking', step: 1, data: { thought: 'hi' }, timestamp: 1 })

      expect(store.events).toHaveLength(1)
      expect(store.events[0].event_type).toBe('thinking')
    })

    it('handles summary events correctly', () => {
      let capturedOnEvent
      postSSE.mockImplementation((_url, _body, { onEvent }) => {
        capturedOnEvent = onEvent
        return { abort: vi.fn() }
      })

      store.startAgentRun('test')
      capturedOnEvent({
        event_type: 'summary',
        run_id: 'run-123',
        status: 'success',
        steps: 5,
        timestamp: 1,
      })

      expect(store.runId).toBe('run-123')
      expect(store.agentStatus).toBe('success')
    })

    it('handles error events correctly', () => {
      let capturedOnEvent
      postSSE.mockImplementation((_url, _body, { onEvent }) => {
        capturedOnEvent = onEvent
        return { abort: vi.fn() }
      })

      store.startAgentRun('test')
      capturedOnEvent({
        event_type: 'error',
        step: 3,
        data: { error: 'LLM failed' },
        timestamp: 1,
      })

      expect(store.error).toBe('LLM failed')
    })

    it('sets running to false on onDone', () => {
      let capturedOnDone
      postSSE.mockImplementation((_url, _body, { onDone }) => {
        capturedOnDone = onDone
        return { abort: vi.fn() }
      })

      store.startAgentRun('test')
      expect(store.running).toBe(true)

      capturedOnDone()
      expect(store.running).toBe(false)
    })

    it('sets error and running=false on onError', () => {
      let capturedOnError
      postSSE.mockImplementation((_url, _body, { onError }) => {
        capturedOnError = onError
        return { abort: vi.fn() }
      })

      store.startAgentRun('test')
      capturedOnError(new Error('network fail'))

      expect(store.error).toBe('network fail')
      expect(store.running).toBe(false)
    })
  })

  describe('stopAgentRun', () => {
    it('calls abort on the SSE handle', () => {
      const abortFn = vi.fn()
      postSSE.mockReturnValue({ abort: abortFn })

      store.startAgentRun('test')
      store.stopAgentRun()

      expect(abortFn).toHaveBeenCalledTimes(1)
      expect(store.running).toBe(false)
    })

    it('does nothing if no active connection', () => {
      store.stopAgentRun()
      expect(store.running).toBe(false)
    })
  })

  describe('clearTrace', () => {
    it('resets all state', () => {
      store.events = [{ event_type: 'thinking', step: 1 }]
      store.runId = 'run-1'
      store.agentStatus = 'success'
      store.error = 'some error'

      store.clearTrace()

      expect(store.events).toEqual([])
      expect(store.runId).toBeNull()
      expect(store.agentStatus).toBeNull()
      expect(store.error).toBeNull()
      expect(store.running).toBe(false)
    })
  })
})
