import { describe, it, expect } from 'vitest'
import {
  resolveEventTagType,
  eventTypeKey,
  resolveActionStatusClass,
  resolveAgentStatusTagType,
  formatEventTime,
  truncateText,
  buildActionSummary,
} from './agent-trace.js'

describe('agent-trace view-model helpers', () => {
  describe('resolveEventTagType', () => {
    it('maps task_analysis to primary', () => {
      expect(resolveEventTagType('task_analysis')).toBe('primary')
    })

    it('maps plan to primary', () => {
      expect(resolveEventTagType('plan')).toBe('primary')
    })

    it('maps thinking to empty string (default)', () => {
      expect(resolveEventTagType('thinking')).toBe('')
    })

    it('maps action to success', () => {
      expect(resolveEventTagType('action')).toBe('success')
    })

    it('maps plan_step_complete to success', () => {
      expect(resolveEventTagType('plan_step_complete')).toBe('success')
    })

    it('maps finish to info', () => {
      expect(resolveEventTagType('finish')).toBe('info')
    })

    it('maps error to danger', () => {
      expect(resolveEventTagType('error')).toBe('danger')
    })

    it('maps summary to info', () => {
      expect(resolveEventTagType('summary')).toBe('info')
    })

    it('maps unknown type to info', () => {
      expect(resolveEventTagType('unknown_type')).toBe('info')
    })
  })

  describe('eventTypeKey', () => {
    it('returns the correct i18n key', () => {
      expect(eventTypeKey('thinking')).toBe('agentTrace.eventTypes.thinking')
      expect(eventTypeKey('action')).toBe('agentTrace.eventTypes.action')
    })
  })

  describe('resolveActionStatusClass', () => {
    it('returns is-success for true', () => {
      expect(resolveActionStatusClass(true)).toBe('is-success')
    })

    it('returns is-danger for false', () => {
      expect(resolveActionStatusClass(false)).toBe('is-danger')
    })
  })

  describe('resolveAgentStatusTagType', () => {
    it('maps success to success', () => {
      expect(resolveAgentStatusTagType('success')).toBe('success')
    })

    it('maps failed to danger', () => {
      expect(resolveAgentStatusTagType('failed')).toBe('danger')
    })

    it('maps error to danger', () => {
      expect(resolveAgentStatusTagType('error')).toBe('danger')
    })

    it('maps max_steps_reached to warning', () => {
      expect(resolveAgentStatusTagType('max_steps_reached')).toBe('warning')
    })

    it('maps unknown status to info', () => {
      expect(resolveAgentStatusTagType('whatever')).toBe('info')
    })
  })

  describe('formatEventTime', () => {
    it('formats a unix timestamp to time string', () => {
      const ts = 1700000000
      const result = formatEventTime(ts)
      expect(typeof result).toBe('string')
      expect(result.length).toBeGreaterThan(0)
    })

    it('returns empty string for falsy input', () => {
      expect(formatEventTime(null)).toBe('')
      expect(formatEventTime(0)).toBe('')
      expect(formatEventTime(undefined)).toBe('')
    })
  })

  describe('truncateText', () => {
    it('returns text unchanged when shorter than maxLen', () => {
      expect(truncateText('short', 120)).toBe('short')
    })

    it('truncates long text with ellipsis', () => {
      const long = 'a'.repeat(200)
      const result = truncateText(long, 50)
      expect(result.length).toBe(51)
      expect(result.endsWith('…')).toBe(true)
    })

    it('handles null/undefined gracefully', () => {
      expect(truncateText(null)).toBe('')
      expect(truncateText(undefined)).toBe('')
      expect(truncateText('')).toBe('')
    })

    it('uses default maxLen of 120', () => {
      const long = 'b'.repeat(200)
      const result = truncateText(long)
      expect(result.length).toBe(121)
    })
  })

  describe('buildActionSummary', () => {
    it('builds summary for a successful action', () => {
      const event = {
        event_type: 'action',
        step: 1,
        data: { tool: 'search_knowledge', success: true, duration_ms: 123 },
      }
      expect(buildActionSummary(event)).toBe('search_knowledge · OK · 123ms')
    })

    it('builds summary for a failed action', () => {
      const event = {
        event_type: 'action',
        step: 2,
        data: { tool: 'execute_script', success: false, duration_ms: 500 },
      }
      expect(buildActionSummary(event)).toBe('execute_script · FAIL · 500ms')
    })

    it('handles missing duration_ms', () => {
      const event = {
        event_type: 'action',
        step: 1,
        data: { tool: 'validate_code', success: true },
      }
      expect(buildActionSummary(event)).toBe('validate_code · OK')
    })

    it('returns empty for non-action events', () => {
      expect(buildActionSummary({ event_type: 'thinking', step: 1 })).toBe('')
    })

    it('returns empty for null', () => {
      expect(buildActionSummary(null)).toBe('')
    })
  })
})
