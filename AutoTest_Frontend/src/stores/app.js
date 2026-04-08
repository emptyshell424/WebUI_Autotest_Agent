import { defineStore } from 'pinia'

import {
  DEFAULT_API_BASE_URL,
  apiClient,
  extractApiError,
  getStoredApiBaseUrl,
  resetApiBaseUrl,
  setApiBaseUrl,
} from '../api/client'

export const useAppStore = defineStore('app', {
  state: () => ({
    apiBaseUrl: getStoredApiBaseUrl(),
    health: null,
    stats: null,
    loadingHealth: false,
    loadingStats: false,
    healthError: '',
    statsError: '',
    rebuildingKnowledge: false,
  }),
  getters: {
    backendConnected: (state) => state.health?.backend?.status === 'healthy' && !state.healthError,
    knowledgeReady: (state) => Boolean(state.health?.knowledge_base?.details?.ready),
    modelConfigured: (state) => Boolean(state.health?.model?.details?.configured),
    overallStatus: (state) => state.health?.status || 'unknown',
  },
  actions: {
    saveApiBaseUrl(baseUrl) {
      this.apiBaseUrl = setApiBaseUrl(baseUrl)
      return this.apiBaseUrl
    },
    restoreDefaultApiBaseUrl() {
      this.apiBaseUrl = resetApiBaseUrl()
      return this.apiBaseUrl
    },
    async fetchHealth() {
      this.loadingHealth = true
      this.healthError = ''
      try {
        const { data } = await apiClient.get('/health')
        this.health = data
        return data
      } catch (error) {
        this.health = null
        this.healthError = extractApiError(error, 'Unable to reach the backend health endpoint.')
        throw error
      } finally {
        this.loadingHealth = false
      }
    },
    async fetchStats() {
      this.loadingStats = true
      this.statsError = ''
      try {
        const { data } = await apiClient.get('/executions/stats')
        this.stats = data.metrics
        return data.metrics
      } catch (error) {
        this.stats = null
        this.statsError = extractApiError(error, 'Unable to load execution metrics.')
        throw error
      } finally {
        this.loadingStats = false
      }
    },
    async rebuildKnowledge() {
      this.rebuildingKnowledge = true
      try {
        const { data } = await apiClient.post('/knowledge/rebuild')
        await Promise.all([this.fetchHealth(), this.fetchStats()])
        return data
      } catch (error) {
        this.healthError = extractApiError(error, 'Knowledge rebuild failed.')
        throw error
      } finally {
        this.rebuildingKnowledge = false
      }
    },
    bootstrap() {
      if (!this.apiBaseUrl) {
        this.apiBaseUrl = DEFAULT_API_BASE_URL
        setApiBaseUrl(this.apiBaseUrl)
      }
    },
  },
})
