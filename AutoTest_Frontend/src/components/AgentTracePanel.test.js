import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import AgentTracePanel from './AgentTracePanel.vue'
import { useAgentStore } from '../stores/agent.js'

// Mock the SSE module
vi.mock('../api/sse.js', () => ({
  postSSE: vi.fn(() => ({ abort: vi.fn() })),
}))

describe('AgentTracePanel', () => {
  let wrapper
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useAgentStore()
    wrapper = mount(AgentTracePanel, {
      global: {
        plugins: [ElementPlus],
      },
    })
  })

  it('renders the panel title', () => {
    expect(wrapper.text()).toContain('Agent Reasoning Trace')
  })

  it('shows empty state when no events', () => {
    expect(wrapper.text()).toContain('Agent Run')
  })

  it('shows streaming indicator when running', async () => {
    store.running = true
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Streaming')
  })

  it('shows waiting message when running but no events', async () => {
    store.running = true
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Connecting to Agent stream')
  })

  it('displays task analysis card', async () => {
    store.events = [
      Object.freeze({
        event_type: 'task_analysis',
        step: 0,
        data: { intent: 'web_test', complexity: 'simple', target_url: 'https://example.com', steps: ['Open page', 'Check title'] },
        timestamp: 1700000000,
      }),
    ]
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Task Analysis')
    expect(wrapper.text()).toContain('web_test')
    expect(wrapper.text()).toContain('simple')
    expect(wrapper.text()).toContain('https://example.com')
    expect(wrapper.text()).toContain('Open page')
    expect(wrapper.text()).toContain('Check title')
  })

  it('displays plan card', async () => {
    store.events = [
      Object.freeze({
        event_type: 'plan',
        step: 0,
        data: {
          goal: 'Login and verify',
          step_count: 2,
          steps: [
            { step_number: 1, description: 'Login', action: 'generate' },
            { step_number: 2, description: 'Verify', action: 'execute' },
          ],
        },
        timestamp: 1700000001,
      }),
    ]
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Execution Plan')
    expect(wrapper.text()).toContain('Login and verify')
    expect(wrapper.text()).toContain('Login')
    expect(wrapper.text()).toContain('Verify')
  })

  it('displays thinking/action step pairs', async () => {
    store.events = [
      Object.freeze({
        event_type: 'thinking',
        step: 1,
        data: { thought: 'I should search knowledge', action: 'search_knowledge' },
        timestamp: 1700000001,
      }),
      Object.freeze({
        event_type: 'action',
        step: 1,
        data: { tool: 'search_knowledge', success: true, observation: 'Found 3 results', duration_ms: 42 },
        timestamp: 1700000002,
      }),
    ]
    await wrapper.vm.$nextTick()
    const text = wrapper.text()
    expect(text).toContain('I should search knowledge')
    expect(text).toContain('search_knowledge')
    expect(text).toContain('OK')
    expect(text).toContain('42ms')
  })

  it('displays error events', async () => {
    store.events = [
      Object.freeze({
        event_type: 'error',
        step: 3,
        data: { error: 'LLM connection failed' },
        timestamp: 1700000003,
      }),
    ]
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('LLM connection failed')
  })

  it('displays finish event', async () => {
    store.events = [
      Object.freeze({
        event_type: 'finish',
        step: 5,
        data: { status: 'success', reason: null },
        timestamp: 1700000005,
      }),
    ]
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Finish')
    expect(wrapper.text()).toContain('success')
  })

  it('displays summary event', async () => {
    store.events = [
      Object.freeze({
        event_type: 'summary',
        run_id: 'run-abc',
        status: 'success',
        steps: 4,
        test_case_id: 'tc-001',
        execution_id: 'exec-001',
        timestamp: 1700000006,
      }),
    ]
    await wrapper.vm.$nextTick()
    const text = wrapper.text()
    expect(text).toContain('Summary')
    expect(text).toContain('run-abc')
    expect(text).toContain('tc-001')
    expect(text).toContain('exec-001')
  })

  it('emits clear event when clear button clicked', async () => {
    const btn = wrapper.findAll('button').find((b) => b.text().includes('Clear'))
    expect(btn).toBeDefined()
    await btn.trigger('click')
    expect(wrapper.emitted('clear')).toHaveLength(1)
  })

  it('shows agent status tag when agentStatus is set', async () => {
    store.agentStatus = 'success'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('success')
  })
})
