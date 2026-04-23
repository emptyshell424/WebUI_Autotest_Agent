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
      <TrendChart
        v-if="trendRows.length"
        :rows="trendRows"
        :labels="chartLabels"
      />

      <div v-if="trendRows.length" class="table-wrap">
        <el-table :data="trendRows" row-key="bucket" max-height="260">
          <el-table-column prop="bucket" :label="t('metrics.trend.date')" min-width="140" />
          <el-table-column prop="execution_count" :label="t('metrics.trend.executions')" width="110" />
          <el-table-column prop="completed_count" :label="t('metrics.trend.firstPass')" width="110" />
          <el-table-column prop="healed_completed_count" :label="t('metrics.trend.healed')" width="110" />
          <el-table-column prop="failed_count" :label="t('metrics.trend.failed')" width="110" />
          <el-table-column prop="blocked_count" :label="t('metrics.trend.blocked')" width="110" />
          <el-table-column :label="t('metrics.trend.finalSuccessRate')" width="130">
            <template #default="{ row }">
              {{ formatRate(row.final_success_rate) }}
            </template>
          </el-table-column>
        </el-table>
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
import { buildMetricCards, formatRate } from '../view-models/metrics'
import TrendChart from '../components/TrendChart.vue'

const appStore = useAppStore()
const { t } = useI18n()

const cards = computed(() => {
  return buildMetricCards(appStore.stats, t)
})

const trendRows = computed(() => appStore.stats?.trend || [])

const chartLabels = computed(() => ({
  firstPass: t('metrics.trend.firstPass'),
  healed: t('metrics.trend.healed'),
  failed: t('metrics.trend.failed'),
  blocked: t('metrics.trend.blocked'),
  successRate: t('metrics.trend.finalSuccessRate'),
}))

const refreshStats = async () => {
  try {
    await appStore.fetchStats()
    ElMessage.success(t('metrics.refreshed'))
  } catch (error) {
    ElMessage.error(appStore.statsError || t('metrics.refreshFailed'))
  }
}
</script>
