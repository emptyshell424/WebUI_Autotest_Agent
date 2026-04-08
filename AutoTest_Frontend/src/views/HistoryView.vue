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
          <el-table-column :label="t('history.outcome')" width="160">
            <template #default="{ row }">
              <span class="status-badge" :data-state="row.status">{{ classifyOutcome(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="test_case_title" :label="t('history.scenario')" min-width="240" />
          <el-table-column prop="self_heal_count" :label="t('history.repairs')" width="100" />
          <el-table-column prop="created_at" :label="t('history.createdAt')" min-width="220" />
          <el-table-column prop="finished_at" :label="t('history.finishedAt')" min-width="220" />
          <el-table-column :label="t('history.actions')" width="120" fixed="right">
            <template #default="{ row }">
              <el-button text @click.stop="selectExecution(row)">{{ t('common.inspect') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <section class="surface-panel --solid">
      <div class="section-title">
        <div>
          <h4>{{ t('common.selectedExecution') }}</h4>
          <p class="section-hint">{{ t('history.selectedHint') }}</p>
        </div>
        <el-button text @click="openInWorkbench" :disabled="!currentExecution">{{ t('history.openInWorkbench') }}</el-button>
      </div>

        <div v-if="currentExecution" class="stack-rows">
          <div class="inline-meta">
            <span>{{ t('workbench.execution') }}: {{ currentExecution.id }}</span>
            <span>{{ t('history.case') }}: {{ currentExecution.test_case_id }}</span>
            <span>{{ t('history.status') }}: {{ formatStatus(currentExecution.status) }}</span>
            <span>{{ t('history.repairs') }}: {{ currentExecution.self_heal_count || 0 }}</span>
          </div>

        <div v-if="currentExecution.validation_errors?.length" class="inline-list">
          <el-tag
            v-for="issue in currentExecution.validation_errors"
            :key="issue"
            type="danger"
            effect="plain"
          >
            {{ issue }}
          </el-tag>
        </div>

        <div class="split-column">
          <div>
            <p class="eyebrow">{{ t('history.executedScript') }}</p>
            <pre class="mono-pane --light">{{ currentExecution.executed_code }}</pre>
          </div>
          <div>
            <p class="eyebrow">{{ t('history.logs') }}</p>
            <pre class="mono-pane">{{ historyOutput }}</pre>
          </div>
        </div>

        <div v-if="currentExecution.self_heal_attempts?.length" class="stack-rows">
          <article
            v-for="attempt in currentExecution.self_heal_attempts"
            :key="attempt.id"
            class="detail-block"
          >
            <div class="section-title --compact">
              <div>
                <p class="eyebrow">{{ t('history.repairAttempt', { count: attempt.attempt_number }) }}</p>
                <h4>{{ formatStatus(attempt.status) }}</h4>
              </div>
              <span class="status-badge" :data-state="attempt.status">{{ formatStatus(attempt.status) }}</span>
            </div>
            <p class="section-hint">{{ attempt.repair_summary || attempt.failure_reason || t('common.noRepairSummary') }}</p>
            <pre class="mono-pane --light">{{ attempt.repaired_code || t('common.noRepairedCode') }}</pre>
          </article>
        </div>
      </div>

      <el-empty v-else :description="t('history.selectToInspect')" />
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'

import { useI18n } from '../i18n'
import { useWorkspaceStore } from '../stores/workspace'

const router = useRouter()
const workspaceStore = useWorkspaceStore()
const { currentExecution, history, loadingHistory } = storeToRefs(workspaceStore)
const { t } = useI18n()

const historyOutput = computed(() => {
  if (!currentExecution.value) {
    return ''
  }
  return [
    '[STDOUT]',
    currentExecution.value.logs || t('common.noStdout'),
    '',
    '[STDERR]',
    currentExecution.value.error || t('common.noStderr'),
  ].join('\n')
})

const formatStatus = (status) => {
  return t(`workbench.status.${status}`)
}

const classifyOutcome = (row) => {
  if (row.status === 'completed') return t('history.outcomeFirstPass')
  if (row.status === 'healed_completed') return t('history.outcomeRepairSuccess')
  if (row.status === 'healed_failed') return t('history.outcomeRepairFailed')
  if (row.status === 'blocked') return t('history.outcomeBlocked')
  return t('history.outcomeRunFailed')
}

const refreshHistory = async () => {
  try {
    const items = await workspaceStore.fetchHistory()
    if (!currentExecution.value && items.length) {
      await workspaceStore.inspectExecution(items[0].id)
    }
    ElMessage.success(t('history.historyRefreshed'))
  } catch (error) {
    ElMessage.error(workspaceStore.lastError || t('history.historyRefreshFailed'))
  }
}

const selectExecution = async (row) => {
  try {
    await workspaceStore.inspectExecution(row.id)
  } catch (error) {
    ElMessage.error(workspaceStore.lastError || t('history.loadExecutionFailed'))
  }
}

const openInWorkbench = () => {
  if (!currentExecution.value) return
  workspaceStore.hydrateFromHistory(currentExecution.value)
  router.push('/')
}

onMounted(async () => {
  if (!history.value.length) {
    await refreshHistory()
    return
  }
  if (!currentExecution.value) {
    await workspaceStore.inspectExecution(history.value[0].id)
  }
})
</script>
