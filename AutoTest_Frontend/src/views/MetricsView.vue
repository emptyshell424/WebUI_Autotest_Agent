<template>
  <div class="view-grid settings-grid">
    <section class="surface-panel">
      <div class="section-title">
        <div>
          <h4>{{ t('metrics.title') }}</h4>
          <p class="section-hint">{{ t('metrics.hint') }}</p>
        </div>
        <el-button text :loading="appStore.loadingStats" @click="refreshStats">{{ t('common.refreshMetrics') }}</el-button>
      </div>

      <el-alert
        v-if="appStore.statsError"
        :title="appStore.statsError"
        type="error"
        :closable="false"
        show-icon
      />

      <div v-if="cards.length" class="detail-grid">
        <article v-for="card in cards" :key="card.label" class="detail-block">
          <p class="eyebrow">{{ card.group }}</p>
          <h4>{{ card.value }}</h4>
          <p class="section-hint">{{ card.label }}</p>
        </article>
      </div>
      <el-empty v-else :description="t('metrics.empty')" />
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'

import { useI18n } from '../i18n'
import { useAppStore } from '../stores/app'

const appStore = useAppStore()
const { t } = useI18n()

const formatRate = (value) => `${Math.round((value || 0) * 100)}%`

const cards = computed(() => {
  if (!appStore.stats) {
    return []
  }

  return [
    { group: t('metrics.groups.volume'), label: t('metrics.labels.generatedCases'), value: appStore.stats.generated_count },
    { group: t('metrics.groups.volume'), label: t('metrics.labels.executionRecords'), value: appStore.stats.execution_count },
    {
      group: t('metrics.groups.success'),
      label: t('metrics.labels.firstPassSuccessRate'),
      value: formatRate(appStore.stats.first_pass_success_rate),
    },
    {
      group: t('metrics.groups.healing'),
      label: t('metrics.labels.selfHealTriggeredRate'),
      value: formatRate(appStore.stats.self_heal_triggered_rate),
    },
    {
      group: t('metrics.groups.healing'),
      label: t('metrics.labels.selfHealSuccessRate'),
      value: formatRate(appStore.stats.self_heal_success_rate),
    },
    {
      group: t('metrics.groups.outcome'),
      label: t('metrics.labels.finalSuccessRate'),
      value: formatRate(appStore.stats.final_success_rate),
    },
  ]
})

const refreshStats = async () => {
  try {
    await appStore.fetchStats()
    ElMessage.success(t('metrics.refreshed'))
  } catch (error) {
    ElMessage.error(appStore.statsError || t('metrics.refreshFailed'))
  }
}
</script>
