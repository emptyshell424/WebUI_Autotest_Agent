import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import WorkbenchView from './WorkbenchView.vue'
import { useWorkspaceStore } from '../stores/workspace.js'

describe('WorkbenchView', () => {
  let wrapper
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useWorkspaceStore()
    wrapper = mount(WorkbenchView, {
      global: {
        plugins: [ElementPlus],
      },
    })
  })

  it('renders the summary strip with status metrics', () => {
    const text = wrapper.text()
    expect(text).toContain('Current status')
    expect(text).toContain('Knowledge hits')
    expect(text).toContain('Latest case')
    expect(text).toContain('Repair attempts')
  })

  it('renders the prompt textarea', () => {
    const textarea = wrapper.find('textarea')
    expect(textarea.exists()).toBe(true)
  })

  it('renders the scenario section', () => {
    expect(wrapper.text()).toContain('Scenario brief')
  })

  it('shows empty trace message when no execution', () => {
    expect(wrapper.text()).toContain('Start a run to see the live execution trace')
  })

  it('shows retrieval mode options', () => {
    const text = wrapper.text()
    expect(text).toContain('Vector only')
    expect(text).toContain('Hybrid retrieval')
  })

  it('displays execution info when execution is set', async () => {
    store.currentExecution = {
      id: 'exec-001',
      test_case_id: 'case-001',
      executed_code: "print('hello')",
      status: 'completed',
      logs: 'Test Completed',
      error: null,
      validation_errors: [],
      created_at: '2026-01-01T00:00:00Z',
      started_at: '2026-01-01T00:00:01Z',
      finished_at: '2026-01-01T00:00:05Z',
      requested_strategy: 'interaction_first',
      effective_strategy: 'interaction_first',
      fallback_reason: null,
      site_profile: null,
      self_heal_triggered: false,
      self_heal_count: 0,
      self_heal_attempts: [],
    }
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('exec-001')
    expect(wrapper.text()).toContain('Completed')
  })
})
