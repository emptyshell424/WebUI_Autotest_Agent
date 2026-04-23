import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { apiClient } from '../api/client.js'
import { useAppStore } from './app.js'

describe('app store', () => {
  let originalGet

  beforeEach(() => {
    setActivePinia(createPinia())
    originalGet = apiClient.get
  })

  afterEach(() => {
    apiClient.get = originalGet
  })

  it('fetches health and runtime settings', async () => {
    const store = useAppStore()
    apiClient.get = async (url) => {
      if (url === '/health') {
        return { data: { status: 'healthy', backend: { status: 'healthy', details: {} }, knowledge_base: { details: { ready: true } }, model: { details: { configured: false } }, storage: { details: {} } } }
      }
      if (url === '/settings') {
        return { data: { settings: { execution_timeout_seconds: 60, max_self_heal_attempts: 1, max_concurrent_executions: 1 } } }
      }
      throw new Error(`unexpected url ${url}`)
    }

    const health = await store.fetchHealth()
    const settings = await store.fetchRuntimeSettings()
    expect(health.status).toBe('healthy')
    expect(settings.max_concurrent_executions).toBe(1)
    expect(store.knowledgeReady).toBe(true)
  })
})
