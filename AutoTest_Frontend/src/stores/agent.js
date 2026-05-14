import { defineStore } from 'pinia'

import { getStoredApiBaseUrl } from '../api/client.js'
import { postSSE } from '../api/sse.js'

export const useAgentStore = defineStore('agent', {
  state: () => ({
    events: [],
    running: false,
    runId: null,
    agentStatus: null,
    error: null,
    _sseHandle: null,
  }),
  getters: {
    hasEvents: (state) => state.events.length > 0,
    taskAnalysis: (state) => state.events.find((e) => e.event_type === 'task_analysis') || null,
    plan: (state) => state.events.find((e) => e.event_type === 'plan') || null,
    thinkingEvents: (state) => state.events.filter((e) => e.event_type === 'thinking'),
    actionEvents: (state) => state.events.filter((e) => e.event_type === 'action'),
    planStepEvents: (state) => state.events.filter((e) => e.event_type === 'plan_step_complete'),
    finishEvent: (state) => state.events.find((e) => e.event_type === 'finish') || null,
    errorEvents: (state) => state.events.filter((e) => e.event_type === 'error'),
    summary: (state) => state.events.find((e) => e.event_type === 'summary') || null,
    stepPairs: (state) => {
      const pairs = []
      const thinking = state.events.filter((e) => e.event_type === 'thinking')
      for (const t of thinking) {
        const action = state.events.find(
          (e) => e.event_type === 'action' && e.step === t.step
        )
        pairs.push({ thinking: t, action: action || null })
      }
      return pairs
    },
  },
  actions: {
    startAgentRun(prompt, maxSteps = 15) {
      this.stopAgentRun()
      this.events = []
      this.running = true
      this.runId = null
      this.agentStatus = null
      this.error = null

      const baseUrl = getStoredApiBaseUrl()
      const url = `${baseUrl}/agent/run/stream`

      this._sseHandle = postSSE(
        url,
        { prompt, max_steps: maxSteps },
        {
          onEvent: (event) => {
            this.events.push(Object.freeze(event))

            if (event.event_type === 'summary') {
              this.runId = event.run_id || null
              this.agentStatus = event.status || null
              if (event.error) {
                this.error = event.error
              }
            }
            if (event.event_type === 'error' && event.data?.error) {
              this.error = event.data.error
            }
          },
          onError: (err) => {
            this.error = err?.message || 'SSE connection failed'
            this.running = false
          },
          onDone: () => {
            this.running = false
            this._sseHandle = null
          },
        }
      )
    },
    stopAgentRun() {
      if (this._sseHandle) {
        this._sseHandle.abort()
        this._sseHandle = null
      }
      this.running = false
    },
    clearTrace() {
      this.stopAgentRun()
      this.events = []
      this.runId = null
      this.agentStatus = null
      this.error = null
    },
  },
})
