<template>
  <div class="view-grid history-grid">
    <section class="surface-panel">
      <div class="section-title">
        <div>
          <h4>{{ t('history.title') }}</h4>
          <p class="section-hint">{{ t('history.hint') }}</p>
        </div>
        <el-button text :icon="RefreshRight" :loading="loadingHistory" @click="refreshHistory">
          {{ t('common.refreshHistory') }}
        </el-button>
      </div>

      <!-- thesis: hide — status filter dropdown hidden
      <div class="toolbar-row">
        <el-select v-model="historyStatusFilter" clearable @change="refreshHistory">
          ...status options...
        </el-select>
      </div>
      -->

      <div class="table-wrap">
        <el-table
          :data="history"
          height="340"
          row-key="id"
          @row-click="selectExecution"
          :empty-text="t('history.empty')"
        >
          <el-table-column prop="status" :label="t('history.status')" width="120">
            <template #default="{ row }">
              <span class="status-badge" :data-state="row.status">{{ formatStatus(row.status) }}</span>
            </template>
          </el-table-column>
          <!-- thesis: hide — outcome column hidden
          <el-table-column :label="t('history.outcome')" width="160">
            ...outcome column...
          </el-table-column>
          -->
          <el-table-column prop="test_case_title" :label="t('history.scenario')" min-width="220" show-overflow-tooltip />
          <!-- thesis: hide — strategy column hidden
          <el-table-column :label="t('history.strategy')" min-width="170">
            ...strategy column...
          </el-table-column>
          -->
          <!-- thesis: hide — repairs column hidden
          <el-table-column prop="self_heal_count" :label="t('history.repairs')" width="100" />
          -->
          <el-table-column prop="created_at" :label="t('history.createdAt')" min-width="220" />
          <el-table-column prop="finished_at" :label="t('history.finishedAt')" min-width="220" />
          <el-table-column :label="t('history.actions')" width="160" fixed="right">
            <template #default="{ row }">
              <el-button text @click.stop="selectExecution(row)">{{ t('common.inspect') }}</el-button>
              <el-button text type="danger" @click.stop="handleCancel(row)" v-if="row.status === 'queued' || row.status === 'running'">{{ t('history.cancel') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <el-pagination
        layout="prev, pager, next, total"
        :page-size="historyLimit"
        :total="historyTotal"
        :current-page="currentPage"
        @current-change="handlePageChange"
      />
    </section>

    <section class="surface-panel --solid">
      <div class="section-title">
        <div>
          <h4>{{ t('common.selectedExecution') }}</h4>
          <p class="section-hint">{{ t('history.selectedHint') }}</p>
        </div>
        <el-button text @click="openInWorkbench" :disabled="!inspectedRecord">{{ t('history.openInWorkbench') }}</el-button>
      </div>

      <div v-if="inspectedRecord" class="stack-rows">
        <div class="inline-meta">
          <span>{{ t('workbench.execution') }}: {{ inspectedRecord.id }}</span>
          <span>{{ t('history.case') }}: {{ inspectedRecord.test_case_id }}</span>
          <span>{{ t('history.status') }}: {{ formatStatus(inspectedRecord.status) }}</span>
          <span>{{ t('history.repairs') }}: {{ inspectedRecord.self_heal_count || 0 }}</span>
        </div>

        <div v-if="inspectedCase" class="detail-block">
          <p class="eyebrow">{{ t('workbench.sectionTitle') }}</p>
          <div class="prompt-display-text">{{ inspectedCase.prompt }}</div>
        </div>

        <!-- thesis: hide — strategy audit hidden
        <div class="detail-block">
          <p class="eyebrow">{{ t('history.strategyAudit') }}</p>
          <div class="inline-meta">
            ...strategy audit...
          </div>
        </div>
        -->

        <div v-if="inspectedRecord.validation_errors?.length" class="inline-list">
          <el-tag
            v-for="issue in inspectedRecord.validation_errors"
            :key="issue"
            type="danger"
            effect="plain"
          >
            {{ issue }}
          </el-tag>
        </div>

        <div v-if="initialFailureReason" class="detail-block">
          <p class="eyebrow">{{ t('history.initialFailureReason') }}</p>
          <pre class="mono-pane --light">{{ initialFailureReason }}</pre>
        </div>

        <div class="split-column">
          <div>
            <p class="eyebrow">{{ t('history.executedScript') }}</p>
            <pre class="mono-pane --light">{{ inspectedRecord.executed_code }}</pre>
          </div>
          <div>
            <p class="eyebrow">{{ t('history.logs') }}</p>
            <pre class="mono-pane">{{ historyOutput }}</pre>
          </div>
        </div>

        <!-- thesis: hide — self_heal_attempts timeline hidden
        <div v-if="inspectedRecord.self_heal_attempts?.length" class="stack-rows">
          ...self_heal_attempts timeline...
        </div>
        -->
      </div>

      <el-empty v-else :description="t('history.selectToInspect')" />
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'

import { useI18n } from '../i18n'
import { useWorkspaceStore } from '../stores/workspace'
import { buildHistoryOutput, classifyOutcome as classifyOutcomeValue } from '../view-models/history'

const router = useRouter()
const workspaceStore = useWorkspaceStore()
const { inspectedRecord, inspectedCase, history, historyTotal, historyLimit, loadingHistory } = storeToRefs(workspaceStore)
const { t } = useI18n()
const historyStatusFilter = ref(workspaceStore.historyStatusFilter)
const currentPage = computed(() => Math.floor(workspaceStore.historyOffset / workspaceStore.historyLimit) + 1)

const historyOutput = computed(() => {
  if (!inspectedRecord.value) {
    return ''
  }
  return buildHistoryOutput(inspectedRecord.value, t)
})

const initialFailureReason = computed(() => {
  if (!inspectedRecord.value) {
    return ''
  }
  return (
    inspectedRecord.value.self_heal_attempts?.[0]?.failure_reason ||
    inspectedRecord.value.error ||
    ''
  )
})

const formatStatus = (status) => {
  return t(`workbench.status.${status}`)
}

const formatStrategy = (value) => {
  return t(`common.strategyLabels.${value || 'interaction_first'}`)
}

const formatSiteProfile = (value) => {
  return t(`common.siteProfileLabels.${value || 'generic'}`)
}

const formatFallbackReason = (value) => {
  return t(`common.fallbackReasonLabels.${value || 'none'}`)
}

const classifyOutcome = (row) => {
  return classifyOutcomeValue(row.status, t)
}

const refreshHistory = async () => {
  try {
    await workspaceStore.fetchHistory({
      offset: 0,
      status: historyStatusFilter.value,
    })
    ElMessage.success(t('history.historyRefreshed'))
  } catch (error) {
    ElMessage.error(workspaceStore.lastError || t('history.historyRefreshFailed'))
  }
}

const handlePageChange = async (page) => {
  try {
    await workspaceStore.fetchHistory({
      offset: (page - 1) * workspaceStore.historyLimit,
      status: historyStatusFilter.value,
    })
  } catch (error) {
    ElMessage.error(workspaceStore.lastError || t('history.historyRefreshFailed'))
  }
}

const selectExecution = async (row) => {
  try {
    await workspaceStore.inspectRecord(row.id)
  } catch (error) {
    ElMessage.error(workspaceStore.lastError || t('history.loadExecutionFailed'))
  }
}

const openInWorkbench = () => {
  if (!inspectedRecord.value) return
  workspaceStore.hydrateFromHistory(inspectedRecord.value)
  router.push('/')
}

const handleCancel = async (row) => {
  try {
    await workspaceStore.cancelExecution(row.id)
    ElMessage.success(t('history.cancelled'))
  } catch (error) {
    ElMessage.error(workspaceStore.lastError || t('history.cancelFailed'))
  }
}

onMounted(async () => {
  if (!history.value.length) {
    await refreshHistory()
  }
})
</script>

