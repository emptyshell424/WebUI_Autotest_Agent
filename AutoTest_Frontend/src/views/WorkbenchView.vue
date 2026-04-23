<template>
  <div class="view-grid workbench-grid">
    <section class="surface-panel">
      <div class="summary-strip">
        <div class="metric-chip">
          <span class="eyebrow">{{ t('workbench.currentStatus') }}</span>
          <strong>{{ statusLabel }}</strong>
        </div>
        <div class="metric-chip">
          <span class="eyebrow">{{ t('workbench.knowledgeHits') }}</span>
          <strong>{{ ragResultCount }}</strong>
        </div>
        <div class="metric-chip">
          <span class="eyebrow">{{ t('workbench.latestCase') }}</span>
          <strong>{{ currentCase?.id?.slice(0, 8) || t('common.notCreated') }}</strong>
        </div>
        <div class="metric-chip">
          <span class="eyebrow">{{ t('workbench.repairAttempts') }}</span>
          <strong>{{ currentExecution?.self_heal_count || 0 }}</strong>
        </div>
      </div>

      <div class="section-title">
        <div>
          <h4>{{ t('workbench.sectionTitle') }}</h4>
          <p class="section-hint">{{ t('workbench.sectionHint') }}</p>
        </div>
      </div>

      <div class="prompt-stack">
        <el-input
          v-model="prompt"
          type="textarea"
          :rows="10"
          resize="none"
          :placeholder="t('workbench.promptPlaceholder')"
        />

        <div class="prompt-actions">
          <el-switch v-model="autoExecute" inline-prompt :active-text="t('workbench.autoRun')" :inactive-text="t('workbench.generateOnly')" />
          <el-radio-group v-model="selectedRetrievalMode" class="mode-radio-group">
            <el-radio-button
              v-for="mode in retrievalModeOptions"
              :key="mode.value"
              :label="mode.value"
            >
              {{ mode.label }}
            </el-radio-button>
          </el-radio-group>
          <el-button type="primary" :icon="MagicStick" :loading="generating" @click="handleGenerate">
            {{ t('workbench.generateScript') }}
          </el-button>
          <el-button :icon="VideoPlay" :disabled="!canRun" :loading="running" @click="handleRun">
            {{ t('workbench.runCurrentScript') }}
          </el-button>
          <el-button text :icon="RefreshRight" @click="refreshCurrentExecution" :disabled="!currentExecution">
            {{ t('workbench.refreshExecution') }}
          </el-button>
        </div>

        <div class="inline-meta">
          <span>{{ t('workbench.selectedRetrievalMode') }}: {{ selectedRetrievalModeLabel }}</span>
          <span>{{ t('workbench.activeRetrievalMode') }}: {{ activeRetrievalModeLabel }}</span>
        </div>

        <el-alert
          v-if="lastError"
          :title="lastError"
          type="error"
          :closable="false"
          show-icon
        />

        <div v-if="knowledgeSources.length" class="inline-list">
          <el-tag v-for="source in knowledgeSources" :key="source" effect="plain">
            {{ source }}
          </el-tag>
        </div>

        <el-alert
          v-if="currentCase?.rag_context"
          :title="t('workbench.knowledgeContext')"
          type="info"
          :closable="false"
          :description="currentCase.rag_context"
          show-icon
        />

        <div v-if="currentCase" class="detail-block">
          <p class="eyebrow">{{ t('workbench.strategyAudit') }}</p>
          <div class="inline-meta">
            <span>{{ t('common.requestedStrategy') }}: {{ formatStrategy(currentCase.requested_strategy) }}</span>
            <span>{{ t('common.effectiveStrategy') }}: {{ formatStrategy(currentCase.effective_strategy) }}</span>
          </div>
        </div>
      </div>
    </section>

    <div class="split-column">
      <section class="surface-panel --solid">
        <div class="section-title">
          <div>
            <h4>{{ t('workbench.generatedScript') }}</h4>
            <p class="section-hint">{{ t('workbench.generatedHint') }}</p>
          </div>
          <span class="status-badge" :data-state="currentStatus">{{ statusLabel }}</span>
        </div>

        <div v-if="latestRepairAttempt" class="detail-block repair-summary">
          <p class="eyebrow">{{ t('workbench.repairSummary') }}</p>
          <h4>{{ t('workbench.attempt', { count: latestRepairAttempt.attempt_number }) }}</h4>
          <p class="section-hint">{{ latestRepairAttempt.repair_summary || t('workbench.repairRetryFallback') }}</p>
        </div>

        <el-input
          v-model="editedCode"
          type="textarea"
          :rows="18"
          resize="none"
          class="code-editor"
          :placeholder="t('workbench.editorPlaceholder')"
        />
      </section>

      <section class="surface-panel">
        <div class="section-title">
          <div>
            <h4>{{ t('workbench.executionTrace') }}</h4>
            <p class="section-hint">{{ t('workbench.executionTraceHint') }}</p>
          </div>
          <div class="execution-state" v-if="currentExecution">
            <el-tag :type="tagType">{{ statusLabel }}</el-tag>
          </div>
        </div>

        <div v-if="currentExecution" class="stack-rows">
          <div class="inline-meta">
            <span>{{ t('workbench.execution') }}: {{ currentExecution.id }}</span>
            <span>{{ t('workbench.started') }}: {{ currentExecution.started_at || t('common.pending') }}</span>
            <span>{{ t('workbench.finished') }}: {{ currentExecution.finished_at || t('common.running') }}</span>
            <span>{{ t('workbench.healing') }}: {{ currentExecution.self_heal_triggered ? t('workbench.repairAttemptsCount', { count: currentExecution.self_heal_count }) : t('common.notTriggered') }}</span>
          </div>

          <div class="detail-block">
            <p class="eyebrow">{{ t('workbench.executionAudit') }}</p>
            <div class="inline-meta">
              <span>{{ t('common.requestedStrategy') }}: {{ formatStrategy(currentExecution.requested_strategy) }}</span>
              <span>{{ t('common.effectiveStrategy') }}: {{ formatStrategy(currentExecution.effective_strategy) }}</span>
              <span>{{ t('common.siteProfile') }}: {{ formatSiteProfile(currentExecution.site_profile) }}</span>
              <span>{{ t('common.fallbackReason') }}: {{ formatFallbackReason(currentExecution.fallback_reason) }}</span>
            </div>
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

          <div v-if="initialFailureReason" class="detail-block">
            <p class="eyebrow">{{ t('workbench.initialFailureReason') }}</p>
            <pre class="mono-pane --light">{{ initialFailureReason }}</pre>
          </div>

          <pre class="mono-pane">{{ executionOutput }}</pre>

          <div v-if="currentExecution.self_heal_attempts?.length" class="stack-rows">
            <div class="section-title --compact">
              <div>
                <h4>{{ t('workbench.repairTimeline') }}</h4>
                <p class="section-hint">{{ t('workbench.repairTimelineHint') }}</p>
              </div>
            </div>

            <article
              v-for="attempt in currentExecution.self_heal_attempts"
              :key="attempt.id"
              class="detail-block"
            >
              <div class="section-title --compact">
                <div>
                  <p class="eyebrow">{{ t('workbench.attempt', { count: attempt.attempt_number }) }}</p>
                  <h4>{{ attempt.status }}</h4>
                </div>
                <span class="status-badge" :data-state="attempt.status">{{ attempt.status }}</span>
              </div>
              <div class="inline-meta">
                <span>{{ t('common.strategyBefore') }}: {{ formatStrategy(attempt.strategy_before) }}</span>
                <span>{{ t('common.strategyAfter') }}: {{ formatStrategy(attempt.strategy_after) }}</span>
                <span>{{ t('common.siteProfile') }}: {{ formatSiteProfile(attempt.site_profile) }}</span>
                <span>{{ t('common.fallbackReason') }}: {{ formatFallbackReason(attempt.fallback_reason) }}</span>
              </div>
              <p class="section-hint">{{ attempt.repair_summary || t('common.noRepairSummary') }}</p>
              <pre class="mono-pane --light">{{ attempt.repaired_code || t('common.noRepairedCode') }}</pre>
            </article>
          </div>
        </div>

        <div v-else class="mono-empty">
          {{ t('workbench.emptyTrace') }}
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { MagicStick, RefreshRight, VideoPlay } from '@element-plus/icons-vue'

import { useI18n } from '../i18n'
import { useWorkspaceStore } from '../stores/workspace'
import { buildExecutionOutput, resolveTagType } from '../view-models/workbench'

const workspaceStore = useWorkspaceStore()
const { t } = useI18n()
const {
  autoExecute,
  canRun,
  currentCase,
  currentExecution,
  currentStatus,
  editedCode,
  activeRetrievalMode,
  generating,
  knowledgeSources,
  lastError,
  latestRepairAttempt,
  prompt,
  ragResultCount,
  running,
} = storeToRefs(workspaceStore)

const selectedRetrievalMode = computed({
  get: () => workspaceStore.retrievalMode,
  set: (value) => {
    workspaceStore.retrievalMode = value
  },
})

const retrievalModeOptions = computed(() => [
  { value: 'vector', label: t('common.retrievalModeLabels.vector') },
  { value: 'hybrid', label: t('common.retrievalModeLabels.hybrid') },
  { value: 'hybrid_rerank', label: t('common.retrievalModeLabels.hybrid_rerank') },
])

const selectedRetrievalModeLabel = computed(() => {
  return t(`common.retrievalModeLabels.${selectedRetrievalMode.value || 'hybrid_rerank'}`)
})

const activeRetrievalModeLabel = computed(() => {
  return t(`common.retrievalModeLabels.${activeRetrievalMode.value || 'hybrid_rerank'}`)
})

const statusLabel = computed(() => {
  return t(`workbench.status.${currentStatus.value}`)
})

const tagType = computed(() => {
  return resolveTagType(currentStatus.value)
})

const executionOutput = computed(() => {
  if (!currentExecution.value) {
    return ''
  }

  return buildExecutionOutput(currentExecution.value, t)
})

const initialFailureReason = computed(() => {
  if (!currentExecution.value) {
    return ''
  }
  return (
    currentExecution.value.self_heal_attempts?.[0]?.failure_reason ||
    currentExecution.value.error ||
    ''
  )
})

const formatStrategy = (value) => {
  return t(`common.strategyLabels.${value || 'interaction_first'}`)
}

const formatSiteProfile = (value) => {
  return t(`common.siteProfileLabels.${value || 'generic'}`)
}

const formatFallbackReason = (value) => {
  return t(`common.fallbackReasonLabels.${value || 'none'}`)
}

const handleGenerate = async () => {
  try {
    await workspaceStore.generateCase(selectedRetrievalMode.value)
    ElMessage.success(
      autoExecute.value ? t('workbench.generatedAndStarted') : t('workbench.generated')
    )
  } catch (error) {
    ElMessage.error(workspaceStore.lastError || t('workbench.generationFailed'))
  }
}

const handleRun = async () => {
  try {
    await workspaceStore.runCurrentCase()
    ElMessage.success(t('workbench.executionCreated'))
  } catch (error) {
    ElMessage.error(workspaceStore.lastError || t('workbench.executionCreateFailed'))
  }
}

const refreshCurrentExecution = async () => {
  if (!currentExecution.value) return
  try {
    await workspaceStore.fetchExecution(currentExecution.value.id)
    ElMessage.success(t('workbench.executionRefreshed'))
  } catch (error) {
    ElMessage.error(workspaceStore.lastError || t('workbench.executionRefreshFailed'))
  }
}
</script>

<style scoped>
.mode-radio-group {
  flex-wrap: wrap;
}
</style>

