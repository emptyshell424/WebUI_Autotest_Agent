import test from 'node:test'
import assert from 'node:assert/strict'

import { createPinia, setActivePinia } from 'pinia'

const clientModule = await import('../api/client.js')
const { useWorkspaceStore } = await import('./workspace.js')

test('workspace store fetchHistory stores pagination state', async () => {
  setActivePinia(createPinia())
  const store = useWorkspaceStore()
  const originalGet = clientModule.apiClient.get
  clientModule.apiClient.get = async (url, options = {}) => {
    if (url === '/executions') {
      return {
        data: {
          items: [{ id: 'e-1', status: 'completed' }],
          total: 12,
        },
      }
    }
    throw new Error(`unexpected url ${url} ${JSON.stringify(options)}`)
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
