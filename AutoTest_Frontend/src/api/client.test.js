import test from 'node:test'
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

const clientModule = await import('./client.js')

test('setApiBaseUrl normalizes and persists the base url', () => {
  const value = clientModule.setApiBaseUrl('http://127.0.0.1:8000/api/v1///')
  assert.equal(value, 'http://127.0.0.1:8000/api/v1')
  assert.equal(clientModule.apiClient.defaults.baseURL, 'http://127.0.0.1:8000/api/v1')
  assert.equal(window.localStorage.getItem('autotest.apiBaseUrl'), 'http://127.0.0.1:8000/api/v1')
})
