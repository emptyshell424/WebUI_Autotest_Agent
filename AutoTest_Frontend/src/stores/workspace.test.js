import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { apiClient } from '../api/client.js'
import { useWorkspaceStore } from './workspace.js'

describe('workspace store', () => {
  let originalGet

  beforeEach(() => {
    setActivePinia(createPinia())
    originalGet = apiClient.get
  })

  afterEach(() => {
    apiClient.get = originalGet
  })

  it('fetchHistory stores pagination state', async () => {
    const store = useWorkspaceStore()
    apiClient.get = async (url, options = {}) => {
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

    await store.fetchHistory({ limit: 10, offset: 10, status: 'completed' })
    expect(store.history).toHaveLength(1)
    expect(store.historyTotal).toBe(12)
    expect(store.historyLimit).toBe(10)
    expect(store.historyOffset).toBe(10)
    expect(store.historyStatusFilter).toBe('completed')
  })
})
