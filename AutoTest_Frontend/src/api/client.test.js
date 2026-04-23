import { describe, it, expect } from 'vitest'
import { setApiBaseUrl, apiClient } from './client.js'

describe('api client', () => {
  it('setApiBaseUrl normalizes and persists the base url', () => {
    const value = setApiBaseUrl('http://127.0.0.1:8000/api/v1///')
    expect(value).toBe('http://127.0.0.1:8000/api/v1')
    expect(apiClient.defaults.baseURL).toBe('http://127.0.0.1:8000/api/v1')
    expect(window.localStorage.getItem('autotest.apiBaseUrl')).toBe('http://127.0.0.1:8000/api/v1')
  })
})
