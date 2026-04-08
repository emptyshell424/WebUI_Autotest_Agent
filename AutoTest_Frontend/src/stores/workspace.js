import { defineStore } from 'pinia'

import { apiClient, extractApiError } from '../api/client'

let executionPoller = null

const ACTIVE_STATUSES = new Set(['queued', 'running'])

export const useWorkspaceStore = defineStore('workspace', {
  state: () => ({
    prompt:
      "Open Baidu, search for DeepSeek, wait for the results page to appear, then print 'Test Completed'.",
    autoExecute: false,
    generating: false,
    running: false,
    loadingHistory: false,
    currentCase: null,
    editedCode: '',
    currentExecution: null,
    knowledgeSources: [],
    ragResultCount: 0,
    history: [],
    lastError: '',
  }),
  getters: {
    hasCurrentCase: (state) => Boolean(state.currentCase),
    canRun: (state) => Boolean(state.currentCase && state.editedCode.trim()),
    currentStatus: (state) => state.currentExecution?.status || state.currentCase?.status || 'idle',
    latestRepairAttempt: (state) => {
      const attempts = state.currentExecution?.self_heal_attempts || []
      return attempts.length ? attempts[attempts.length - 1] : null
    },
  },
  actions: {
    async generateCase() {
      this.generating = true
      this.lastError = ''
      try {
        const { data } = await apiClient.post('/generate', {
          prompt: this.prompt,
        })
        this.currentCase = data.case
        this.editedCode = data.case.generated_code
        this.knowledgeSources = data.knowledge_sources
        this.ragResultCount = data.rag_result_count
        if (this.autoExecute) {
          await this.runCurrentCase()
        }
        return data
      } catch (error) {
        this.lastError = extractApiError(error, 'Generation failed.')
        throw error
      } finally {
        this.generating = false
      }
    },
    async runCurrentCase() {
      if (!this.currentCase) {
        throw new Error('Generate a case before running it.')
      }
      this.running = true
      this.lastError = ''
      try {
        const payload = {
          test_case_id: this.currentCase.id,
          code_override:
            this.editedCode !== this.currentCase.generated_code ? this.editedCode : null,
        }
        const { data } = await apiClient.post('/executions', payload)
        this.currentExecution = data
        this.startPolling(data.id)
        await this.fetchHistory()
        return data
      } catch (error) {
        this.lastError = extractApiError(error, 'Execution failed to start.')
        throw error
      } finally {
        this.running = false
      }
    },
    async fetchExecution(executionId) {
      const { data } = await apiClient.get(`/executions/${executionId}`)
      this.currentExecution = data
      return data
    },
    async fetchHistory() {
      this.loadingHistory = true
      try {
        const { data } = await apiClient.get('/executions', {
          params: { limit: 30, offset: 0 },
        })
        this.history = data.items
        return data.items
      } catch (error) {
        this.lastError = extractApiError(error, 'Unable to load execution history.')
        throw error
      } finally {
        this.loadingHistory = false
      }
    },
    async inspectExecution(executionId) {
      const record = await this.fetchExecution(executionId)
      const latestRepairedCode = record.self_heal_attempts?.at?.(-1)?.repaired_code
      this.editedCode = latestRepairedCode || record.executed_code || ''
      return record
    },
    hydrateFromHistory(record) {
      this.currentExecution = record
      const latestRepairedCode = record.self_heal_attempts?.at?.(-1)?.repaired_code
      this.editedCode = latestRepairedCode || record.executed_code || ''
    },
    startPolling(executionId) {
      this.stopPolling()
      const poll = async () => {
        try {
          const record = await this.fetchExecution(executionId)
          if (!ACTIVE_STATUSES.has(record.status)) {
            this.stopPolling()
            await this.fetchHistory()
          }
        } catch (error) {
          this.lastError = extractApiError(error, 'Unable to refresh execution status.')
          this.stopPolling()
        }
      }
      poll()
      executionPoller = window.setInterval(poll, 2000)
    },
    stopPolling() {
      if (executionPoller) {
        window.clearInterval(executionPoller)
        executionPoller = null
      }
    },
  },
})
