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

const workspaceStore = useWorkspaceStore()
const { t } = useI18n()
const {
  autoExecute,
  canRun,
  currentCase,
  currentExecution,
  currentStatus,
  editedCode,
  generating,
  knowledgeSources,
  lastError,
  latestRepairAttempt,
  prompt,
  ragResultCount,
  running,
} = storeToRefs(workspaceStore)

const statusLabel = computed(() => {
  return t(`workbench.status.${currentStatus.value}`)
})

const tagType = computed(() => {
  if (currentStatus.value === 'completed' || currentStatus.value === 'healed_completed') return 'success'
  if (currentStatus.value === 'failed' || currentStatus.value === 'blocked') return 'danger'
  if (currentStatus.value === 'healed_failed') return 'warning'
  if (currentStatus.value === 'queued' || currentStatus.value === 'running') return 'warning'
  return 'info'
})

const executionOutput = computed(() => {
  if (!currentExecution.value) {
    return ''
  }

  const logs = currentExecution.value.logs || t('common.noStdout')
  const error = currentExecution.value.error || t('common.noStderr')

  return ['[STDOUT]', logs, '', '[STDERR]', error].join('\n')
})

const handleGenerate = async () => {
  try {
    await workspaceStore.generateCase()
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
