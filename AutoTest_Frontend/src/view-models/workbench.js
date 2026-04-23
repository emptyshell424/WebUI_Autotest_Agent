export const buildExecutionOutput = (execution, t) => {
  if (!execution) return ''
  const logs = execution.logs || t('common.noStdout')
  const error = execution.error || t('common.noStderr')
  return ['[STDOUT]', logs, '', '[STDERR]', error].join('\n')
}

export const resolveTagType = (status) => {
  if (status === 'completed' || status === 'healed_completed') return 'success'
  if (status === 'failed' || status === 'blocked') return 'danger'
  if (status === 'healed_failed') return 'warning'
  if (status === 'queued' || status === 'running') return 'warning'
  return 'info'
}
