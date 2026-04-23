import assert from 'node:assert/strict'

global.window = {
  localStorage: {
    store: new Map(),
    getItem(key) {
      return this.store.get(key) ?? null
    },
    setItem(key, value) {
      this.store.set(key, value)
    },
    removeItem(key) {
      this.store.delete(key)
    },
  },
}

const results = []

const run = async (name, fn) => {
  try {
    await fn()
    results.push({ name, status: 'ok' })
  } catch (error) {
    results.push({ name, status: 'failed', error })
  }
}

const clientModule = await import('../src/api/client.js')
const { createPinia, setActivePinia } = await import('pinia')
const { useAppStore } = await import('../src/stores/app.js')
const { useWorkspaceStore } = await import('../src/stores/workspace.js')
const historyHelpers = await import('../src/view-models/history.js')
const metricHelpers = await import('../src/view-models/metrics.js')
const workbenchHelpers = await import('../src/view-models/workbench.js')

await run('api client normalizes and persists the base url', async () => {
  const value = clientModule.setApiBaseUrl('http://127.0.0.1:8000/api/v1///')
  assert.equal(value, 'http://127.0.0.1:8000/api/v1')
  assert.equal(clientModule.apiClient.defaults.baseURL, 'http://127.0.0.1:8000/api/v1')
  assert.equal(window.localStorage.getItem('autotest.apiBaseUrl'), 'http://127.0.0.1:8000/api/v1')
})

await run('app store fetches health and runtime settings', async () => {
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

await run('workspace store fetchHistory stores pagination state', async () => {
  setActivePinia(createPinia())
  const store = useWorkspaceStore()
  const originalGet = clientModule.apiClient.get
  clientModule.apiClient.get = async (url) => {
    if (url === '/executions') {
      return { data: { items: [{ id: 'e-1', status: 'completed' }], total: 12 } }
    }
    throw new Error(`unexpected url ${url}`)
  }
  try {
    await store.fetchHistory({ limit: 10, offset: 10, status: 'completed' })
    assert.equal(store.history.length, 1)
    assert.equal(store.historyTotal, 12)
    assert.equal(store.historyLimit, 10)
    assert.equal(store.historyOffset, 10)
    assert.equal(store.historyStatusFilter, 'completed')
  } finally {
    clientModule.apiClient.get = originalGet
  }
})

await run('history helpers classify and format output', async () => {
  const t = (key) => key
  assert.equal(historyHelpers.classifyOutcome('healed_completed', t), 'history.outcomeRepairSuccess')
  const output = historyHelpers.buildHistoryOutput({ logs: 'done', error: '' }, t)
  assert.match(output, /\[STDOUT\]/)
})

await run('metric helpers build cards and rates', async () => {
  const t = (key) => key
  assert.equal(metricHelpers.formatRate(0.666), '67%')
  const cards = metricHelpers.buildMetricCards(
    {
      generated_count: 1,
      execution_count: 2,
      first_pass_success_rate: 0.5,
      self_heal_triggered_rate: 0.5,
      self_heal_success_rate: 1,
      final_success_rate: 1,
    },
    t
  )
  assert.equal(cards.length, 6)
})

await run('workbench helpers resolve tag and format output', async () => {
  const t = (key) => key
  assert.equal(workbenchHelpers.resolveTagType('completed'), 'success')
  const output = workbenchHelpers.buildExecutionOutput({ logs: 'ok', error: 'boom' }, t)
  assert.match(output, /boom/)
})

for (const result of results) {
  if (result.status === 'ok') {
    console.log(`ok - ${result.name}`)
    continue
  }
  console.error(`not ok - ${result.name}`)
  console.error(result.error)
}

if (results.some((result) => result.status === 'failed')) {
  process.exit(1)
}
