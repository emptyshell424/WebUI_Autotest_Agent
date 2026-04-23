import test from 'node:test'
import assert from 'node:assert/strict'

import { createPinia, setActivePinia } from 'pinia'

global.window = {
  localStorage: {
    store: new Map(),
    getItem(key) {
      return this.store.get(key) ?? null
    },
    setItem(key, value) {
      this.store.set(key, value)
    },
  },
}

const clientModule = await import('../api/client.js')
const { useAppStore } = await import('./app.js')

test('app store fetches health and runtime settings', async () => {
  setActivePinia(createPinia())
  const store = useAppStore()
  const originalGet = clientModule.apiClient.get
  clientModule.apiClient.get = async (url) => {
    if (url === '/health') {
      return { data: { status: 'healthy', backend: { status: 'healthy', details: {} }, knowledge_base: { details: { ready: true } }, model: { details: { configured: false } }, storage: { details: {} } } }
    }
    if (url === '/settings') {
      return { data: { settings: { execution_timeout_seconds: 60, max_self_heal_attempts: 1, max_concurrent_executions: 1 } } }
    }
    throw new Error(`unexpected url ${url}`)
  }

  try {
    const health = await store.fetchHealth()
    const settings = await store.fetchRuntimeSettings()
    assert.equal(health.status, 'healthy')
    assert.equal(settings.max_concurrent_executions, 1)
    assert.equal(store.knowledgeReady, true)
  } finally {
    clientModule.apiClient.get = originalGet
  }
})
