export const formatRate = (value) => `${Math.round((value || 0) * 100)}%`

export const buildMetricCards = (stats, t) => {
  if (!stats) return []
  return [
    { group: t('metrics.groups.volume'), label: t('metrics.labels.generatedCases'), value: stats.generated_count },
    { group: t('metrics.groups.volume'), label: t('metrics.labels.executionRecords'), value: stats.execution_count },
    {
      group: t('metrics.groups.success'),
      label: t('metrics.labels.firstPassSuccessRate'),
      value: formatRate(stats.first_pass_success_rate),
    },
    {
      group: t('metrics.groups.healing'),
      label: t('metrics.labels.selfHealTriggeredRate'),
      value: formatRate(stats.self_heal_triggered_rate),
    },
    {
      group: t('metrics.groups.healing'),
      label: t('metrics.labels.selfHealSuccessRate'),
      value: formatRate(stats.self_heal_success_rate),
    },
    {
      group: t('metrics.groups.outcome'),
      label: t('metrics.labels.finalSuccessRate'),
      value: formatRate(stats.final_success_rate),
    },
  ]
}
