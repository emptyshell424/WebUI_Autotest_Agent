/**
 * Pure helper functions for the AgentTracePanel component.
 */

/**
 * Map event_type to an Element Plus tag type for visual styling.
 */
export const resolveEventTagType = (eventType) => {
  switch (eventType) {
    case 'task_analysis':
      return 'primary'
    case 'plan':
      return 'primary'
    case 'thinking':
      return ''
    case 'action':
      return 'success'
    case 'plan_step_complete':
      return 'success'
    case 'finish':
      return 'info'
    case 'error':
      return 'danger'
    case 'summary':
      return 'info'
    default:
      return 'info'
  }
}

/**
 * Map event_type to an i18n label key under `agentTrace.eventTypes.*`.
 */
export const eventTypeKey = (eventType) => `agentTrace.eventTypes.${eventType}`

/**
 * Determine a CSS status class for the action result.
 */
export const resolveActionStatusClass = (success) => {
  return success ? 'is-success' : 'is-danger'
}

/**
 * Resolve the overall agent status to a tag type.
 */
export const resolveAgentStatusTagType = (status) => {
  if (status === 'success') return 'success'
  if (status === 'failed' || status === 'error') return 'danger'
  if (status === 'max_steps_reached') return 'warning'
  return 'info'
}

/**
 * Format a timestamp (seconds since epoch) to a short time string.
 */
export const formatEventTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    const date = new Date(timestamp * 1000)
    return date.toLocaleTimeString()
  } catch {
    return ''
  }
}

/**
 * Truncate a string for display in compact views.
 */
export const truncateText = (text, maxLen = 120) => {
  if (!text) return ''
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen) + '…'
}

/**
 * Build a compact summary line for an action event.
 */
export const buildActionSummary = (event) => {
  if (!event || event.event_type !== 'action') return ''
  const tool = event.data?.tool || '?'
  const ok = event.data?.success ? 'OK' : 'FAIL'
  const ms = event.data?.duration_ms != null ? `${event.data.duration_ms}ms` : ''
  return [tool, ok, ms].filter(Boolean).join(' · ')
}
