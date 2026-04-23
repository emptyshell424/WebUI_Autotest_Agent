export const classifyOutcome = (status, t) => {
  if (status === 'completed') return t('history.outcomeFirstPass')
  if (status === 'healed_completed') return t('history.outcomeRepairSuccess')
  if (status === 'healed_failed') return t('history.outcomeRepairFailed')
  if (status === 'blocked') return t('history.outcomeBlocked')
  if (status === 'cancelled') return t('workbench.status.cancelled')
  return t('history.outcomeRunFailed')
}

export const buildHistoryOutput = (execution, t) => {
  if (!execution) return ''
  return [
    '[STDOUT]',
    execution.logs || t('common.noStdout'),
    '',
    '[STDERR]',
    execution.error || t('common.noStderr'),
  ].join('\n')
}
