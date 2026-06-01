<template>
  <div class="view-grid workbench-grid">
    <section class="surface-panel">
      <div class="summary-strip">
        <div class="metric-chip">
          <span class="eyebrow">{{ t('workbench.currentStatus') }}</span>
          <strong>{{ statusLabel }}</strong>
        </div>
        <div class="metric-chip">
          <span class="eyebrow">{{ t('workbench.latestCase') }}</span>
          <strong>{{ currentCase?.id?.slice(0, 8) || t('common.notCreated') }}</strong>
        </div>
        <!-- thesis: hide — knowledgeHits and repairAttempts hidden
        <div class="metric-chip">
          <span class="eyebrow">{{ t('workbench.knowledgeHits') }}</span>
          <strong>{{ ragResultCount }}</strong>
        </div>
        <div class="metric-chip">
          <span class="eyebrow">{{ t('workbench.repairAttempts') }}</span>
          <strong>{{ currentExecution?.self_heal_count || 0 }}</strong>
        </div>
        -->
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
          <!-- thesis: three-mode comparison buttons -->
          <el-button
            :type="activeMode === 'a' ? 'primary' : 'default'"
            :icon="VideoPlay"
            :disabled="!prompt?.trim()"
            :loading="activeMode === 'a' && (generating || running)"
            @click="handleModeA"
          >
            {{ t('workbench.modeA') }}
          </el-button>
          <el-button
            :type="activeMode === 'b' ? 'primary' : 'default'"
            :icon="MagicStick"
            :disabled="!prompt?.trim()"
            :loading="activeMode === 'b' && generating"
            @click="handleGenerate"
          >
            {{ t('workbench.modeB') }}
          </el-button>
          <el-button
            :type="activeMode === 'c' ? 'primary' : 'success'"
            :icon="Cpu"
            :disabled="!prompt?.trim() || agentRunning"
            @click="handleAgentRun"
          >
            {{ t('workbench.modeC') }}
          </el-button>

          <el-button
            v-if="activeMode !== 'c' && !agentRunning"
            :disabled="!canRun"
            :loading="running"
            @click="handleRun"
          >
            {{ t('workbench.runCurrentScript') }}
          </el-button>
          <el-button
            v-if="activeMode === 'c' && agentRunning"
            type="danger"
            :icon="Close"
            @click="handleAgentStop"
          >
            {{ t('agentTrace.agentStop') }}
          </el-button>
          <el-button text :icon="RefreshRight" @click="refreshCurrentExecution" :disabled="!currentExecution || activeMode === 'c'">
            {{ t('workbench.refreshExecution') }}
          </el-button>
        </div>

        <!-- thesis: hide — autoExecute switch
        <el-switch v-model="autoExecute" ... />
        -->

        <!-- thesis: hide — RAG retrieval mode radio group
        <el-radio-group v-model="selectedRetrievalMode" ...></el-radio-group>
        -->

        <!-- thesis: hide — retrieval mode display
        <div class="inline-meta">
          <span>{{ t('workbench.selectedRetrievalMode') }}: {{ selectedRetrievalModeLabel }}</span>
          <span>{{ t('workbench.activeRetrievalMode') }}: {{ activeRetrievalModeLabel }}</span>
        </div>
        -->

        <el-alert
          v-if="lastError"
          :title="lastError"
          type="error"
          :closable="false"
          show-icon
        />

        <!-- thesis: hide — knowledge sources tags
        <div v-if="knowledgeSources.length" class="inline-list">
          <el-tag v-for="source in knowledgeSources" :key="source" effect="plain">
            {{ source }}
          </el-tag>
        </div>
        -->

        <!-- thesis: hide — RAG context alert
        <el-alert
          v-if="currentCase?.rag_context"
          :title="t('workbench.knowledgeContext')"
          type="info"
          :closable="false"
          :description="currentCase.rag_context"
          show-icon
        />
        -->

        <!-- thesis: hide — strategy audit
        <div v-if="currentCase" class="detail-block">
          <p class="eyebrow">{{ t('workbench.strategyAudit') }}</p>
          <div class="inline-meta">
            <span>{{ t('common.requestedStrategy') }}: {{ formatStrategy(currentCase.requested_strategy) }}</span>
            <span>{{ t('common.effectiveStrategy') }}: {{ formatStrategy(currentCase.effective_strategy) }}</span>
          </div>
        </div>
        -->
      </div>
    </section>

    <div class="split-column">
      <!-- Progress strip for modes A/B -->
      <div v-if="activeMode === 'a' || activeMode === 'b'" class="progress-strip">
        <div class="prog-step" :class="{ active: generating, done: currentCase }">
          <span class="prog-dot" />
          <span class="prog-label">{{ t('workbench.stepGenerate') }}</span>
        </div>
        <div class="prog-line" :class="{ done: currentCase }" />
        <div class="prog-step" :class="executeStepClass">
          <span class="prog-dot" />
          <span class="prog-label">{{ t('workbench.stepExecute') }}</span>
        </div>
      </div>

      <Transition name="panel-fade" mode="out-in">
        <div v-if="activeMode === 'a' || activeMode === 'b'" key="script">
          <section class="surface-panel --solid">
            <div class="section-title">
              <div>
                <h4>{{ t('workbench.generatedScript') }}</h4>
                <p class="section-hint">{{ t('workbench.generatedHint') }}</p>
              </div>
              <span class="status-badge" :data-state="currentStatus">{{ statusLabel }}</span>
            </div>

            <CodeEditor
              v-model="editedCode"
              :rows="18"
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

              <pre class="mono-pane">{{ executionOutput }}</pre>
            </div>

            <div v-else class="mono-empty">
              {{ t('workbench.emptyTrace') }}
            </div>
          </section>
        </div>

        <AgentTracePanel v-else-if="activeMode === 'c'" key="agent" @clear="handleAgentClear" />
        <div v-else key="empty" class="mono-empty">
          {{ t('workbench.selectModeHint') }}
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { Close, Cpu, MagicStick, RefreshRight, VideoPlay } from '@element-plus/icons-vue'

import { useI18n } from '../i18n'
import { useWorkspaceStore } from '../stores/workspace'
import { useAgentStore } from '../stores/agent'
import { buildExecutionOutput, resolveTagType } from '../view-models/workbench'
import CodeEditor from '../components/CodeEditor.vue'
import AgentTracePanel from '../components/AgentTracePanel.vue'

const workspaceStore = useWorkspaceStore()
const agentStore = useAgentStore()
const { t } = useI18n()

const activeMode = ref(null) // 'a' | 'b' | 'c' | null

const agentRunning = computed(() => agentStore.running)
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

const executeStepClass = computed(() => {
  if (running.value) return { active: true }
  const s = currentStatus.value
  if (s === 'completed' || s === 'healed_completed') return { done: true }
  if (s === 'failed' || s === 'healed_failed' || s === 'blocked') return { failed: true }
  return {}
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

const handleModeA = async () => {
  activeMode.value = 'a'
  agentStore.clearTrace()
  try {
    await workspaceStore.generateCase(selectedRetrievalMode.value)
    ElMessage.success(t('workbench.generated'))
    if (currentCase.value) {
      await workspaceStore.runCurrentCase()
    }
  } catch (error) {
    ElMessage.error(workspaceStore.lastError || t('workbench.generationFailed'))
  }
}

const handleGenerate = async () => {
  activeMode.value = 'b'
  agentStore.clearTrace()
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

const handleAgentRun = () => {
  const text = prompt.value?.trim()
  if (!text) return
  activeMode.value = 'c'
  workspaceStore.currentExecution = null
  workspaceStore.currentCase = null
  workspaceStore.editedCode = ''
  agentStore.startAgentRun(text)
  ElMessage.success(t('agentTrace.agentRunStarted'))
}

const handleAgentStop = () => {
  agentStore.stopAgentRun()
  ElMessage.info(t('agentTrace.agentStopped'))
}

const handleAgentClear = () => {
  agentStore.clearTrace()
  ElMessage.info(t('agentTrace.agentCleared'))
}

defineExpose({ activeMode })
</script>

<style scoped>
/* ---- Transition ---- */
.panel-fade-enter-active,
.panel-fade-leave-active {
  transition: opacity 0.2s ease;
}
.panel-fade-enter-from,
.panel-fade-leave-to {
  opacity: 0;
}

/* ---- Progress strip ---- */
.progress-strip {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 10px 18px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid var(--line);
  margin-bottom: 4px;
}

.prog-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--ink-soft);
  transition: color 0.25s;
}
.prog-step.active {
  color: var(--accent);
  font-weight: 600;
}
.prog-step.done {
  color: var(--success);
}
.prog-step.failed {
  color: var(--danger);
}

.prog-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--line);
  flex-shrink: 0;
  transition: background 0.25s, box-shadow 0.25s;
}
.prog-step.active .prog-dot {
  background: var(--accent);
  box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.18);
  animation: dotPulse 1.2s infinite;
}
.prog-step.done .prog-dot {
  background: var(--success);
}
.prog-step.failed .prog-dot {
  background: var(--danger);
}

.prog-line {
  flex: 1;
  height: 2px;
  background: var(--line);
  margin: 0 14px;
  min-width: 40px;
  transition: background 0.4s;
}
.prog-line.done {
  background: var(--success);
}

.prog-label {
  white-space: nowrap;
}

@keyframes dotPulse {
  0%, 100% { box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.18); }
  50% { box-shadow: 0 0 0 8px rgba(64, 158, 255, 0.06); }
}
</style>

