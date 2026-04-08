import axios from 'axios'

const STORAGE_KEY = 'autotest.apiBaseUrl'
const DEFAULT_API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

const normalizeBaseUrl = (baseUrl) => {
  const trimmed = (baseUrl || '').trim()
  return trimmed.replace(/\/+$/, '')
}

const apiClient = axios.create({
  timeout: 60000,
})

const hasWindow = typeof window !== 'undefined'

export const getStoredApiBaseUrl = () => {
  const stored = hasWindow ? window.localStorage.getItem(STORAGE_KEY) : null
  return normalizeBaseUrl(stored || DEFAULT_API_BASE_URL)
}

export const setApiBaseUrl = (baseUrl) => {
  const normalized = normalizeBaseUrl(baseUrl)
  apiClient.defaults.baseURL = normalized
  if (hasWindow) {
    window.localStorage.setItem(STORAGE_KEY, normalized)
  }
  return normalized
}

export const resetApiBaseUrl = () => setApiBaseUrl(DEFAULT_API_BASE_URL)

export const extractApiError = (error, fallbackMessage) => {
  return (
    error?.response?.data?.message ||
    error?.response?.data?.detail ||
    error?.message ||
    fallbackMessage
  )
}

setApiBaseUrl(getStoredApiBaseUrl())

export { apiClient, DEFAULT_API_BASE_URL }
