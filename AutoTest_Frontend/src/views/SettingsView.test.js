import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import SettingsView from './SettingsView.vue'
import { useAppStore } from '../stores/app.js'

describe('SettingsView', () => {
  let wrapper
  let appStore

  beforeEach(() => {
    setActivePinia(createPinia())
    appStore = useAppStore()
    wrapper = mount(SettingsView, {
      global: {
        plugins: [ElementPlus],
      },
    })
  })

  it('renders the connection section title', () => {
    expect(wrapper.text()).toContain('Connection and defaults')
  })

  it('renders the runtime limits section', () => {
    expect(wrapper.text()).toContain('Runtime limits')
  })

  it('renders form labels for runtime settings', () => {
    const text = wrapper.text()
    expect(text).toContain('Execution timeout (seconds)')
    expect(text).toContain('Max self-heal attempts')
    expect(text).toContain('Max concurrent executions')
  })

  it('renders the API base URL input', () => {
    const input = wrapper.find('input.el-input__inner')
    expect(input.exists()).toBe(true)
  })

  it('renders health sections when health data is available', async () => {
    appStore.health = {
      status: 'healthy',
      backend: { status: 'healthy', details: {} },
      model: { status: 'degraded', details: { configured: false } },
      knowledge_base: { status: 'healthy', details: { ready: true } },
      storage: { status: 'healthy', details: {} },
    }
    await wrapper.vm.$nextTick()
    const text = wrapper.text()
    expect(text).toContain('API service')
    expect(text).toContain('LLM runtime')
    expect(text).toContain('Knowledge base')
    expect(text).toContain('Local runtime')
  })

  it('shows error alert when settingsError is set', async () => {
    appStore.settingsError = 'Something went wrong'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Something went wrong')
  })
})
