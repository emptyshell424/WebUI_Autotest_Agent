<template>
  <section ref="scrollContainer" class="surface-panel agent-trace-panel">
    <div class="section-title">
      <div>
        <h4>{{ t('agentTrace.title') }}</h4>
        <p class="section-hint">{{ t('agentTrace.hint') }}</p>
      </div>
      <div class="agent-trace-actions">
        <el-tag v-if="agentStatus" :type="statusTagType" effect="dark" size="small">
          {{ agentStatus }}
        </el-tag>
        <el-tag v-if="running" type="warning" effect="dark" size="small" class="pulse-tag">
          {{ t('agentTrace.streaming') }}
        </el-tag>
        <el-button text size="small" @click="emit('clear')" :disabled="running">
          {{ t('agentTrace.clear') }}
        </el-button>
      </div>
    </div>

    <!-- Task analysis card -->
    <div v-if="taskAnalysis" class="trace-card trace-card--analysis">
      <p class="eyebrow">{{ t('agentTrace.eventTypes.task_analysis') }}</p>
      <div class="inline-meta">
        <span>{{ t('agentTrace.intent') }}: {{ taskAnalysis.data?.intent || '-' }}</span>
        <span>{{ t('agentTrace.complexity') }}: {{ taskAnalysis.data?.complexity || '-' }}</span>
        <span>{{ t('agentTrace.targetUrl') }}: {{ taskAnalysis.data?.target_url || '-' }}</span>
      </div>
      <div v-if="taskAnalysis.data?.steps?.length" class="trace-steps-list">
        <span v-for="(step, idx) in taskAnalysis.data.steps" :key="idx" class="trace-step-chip">
          {{ idx + 1 }}. {{ step }}
        </span>
      </div>
    </div>

    <!-- Execution plan card -->
    <div v-if="plan" class="trace-card trace-card--plan">
      <p class="eyebrow">{{ t('agentTrace.eventTypes.plan') }}</p>
      <div class="inline-meta">
        <span>{{ t('agentTrace.goal') }}: {{ plan.data?.goal || '-' }}</span>
        <span>{{ t('agentTrace.planSteps') }}: {{ plan.data?.step_count || plan.data?.steps?.length || 0 }}</span>
      </div>
      <div v-if="plan.data?.steps?.length" class="trace-steps-list">
        <div v-for="ps in plan.data.steps" :key="ps.step_number" class="trace-plan-step">
          <el-tag size="small" :type="planStepStatus(ps.step_number)">
            #{{ ps.step_number }}
          </el-tag>
          <span class="trace-plan-desc">{{ ps.description }}</span>
          <span class="muted">{{ ps.action }}</span>
        </div>
      </div>
    </div>

    <!-- Timeline of thinking/action pairs -->
    <div v-if="stepPairs.length" class="trace-timeline">
      <div v-for="(pair, idx) in stepPairs" :key="pair.thinking.step" class="trace-step-group" :class="{ 'trace-step-group--active': idx === stepPairs.length - 1 && running }">
        <!-- Thinking -->
        <div class="trace-row trace-row--thinking">
          <div class="trace-step-num">{{ pair.thinking.step }}</div>
          <div class="trace-row-body">
            <div class="trace-row-header">
              <el-tag size="small">{{ t('agentTrace.eventTypes.thinking') }}</el-tag>
              <span class="muted">{{ formatEventTime(pair.thinking.timestamp) }}</span>
            </div>
            <p class="trace-thought">{{ pair.thinking.data?.thought || '-' }}</p>
            <span class="trace-action-label">→ {{ pair.thinking.data?.action || '?' }}</span>
          </div>
        </div>

        <!-- Action / Observation -->
        <div v-if="pair.action" class="trace-row trace-row--action">
          <div class="trace-step-num"></div>
          <div class="trace-row-body">
            <div class="trace-row-header">
              <el-tag size="small" :type="pair.action.data?.success ? 'success' : 'danger'">
                {{ pair.action.data?.tool || '?' }}
              </el-tag>
              <span :class="pair.action.data?.success ? 'is-success' : 'is-danger'">
                {{ pair.action.data?.success ? 'OK' : 'FAIL' }}
              </span>
              <span class="muted" v-if="pair.action.data?.duration_ms != null">
                {{ pair.action.data.duration_ms }}ms
              </span>
            </div>
            <pre v-if="pair.action.data?.observation" class="trace-observation">{{ truncateText(pair.action.data.observation, 300) }}</pre>
          </div>
        </div>

        <!-- Plan step complete (if any for this step) -->
        <div
          v-for="psc in planStepsForStep(pair.thinking.step)"
          :key="'psc-' + psc.data?.step_number"
          class="trace-row trace-row--plan-step"
        >
          <div class="trace-step-num"></div>
          <div class="trace-row-body">
            <div class="trace-row-header">
              <el-tag size="small" :type="psc.data?.status === 'completed' ? 'success' : 'warning'">
                {{ t('agentTrace.planStepComplete', { n: psc.data?.step_number }) }}
              </el-tag>
              <span class="muted">{{ psc.data?.description || '' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Error events -->
    <div v-for="err in errorEvents" :key="'err-' + err.step" class="trace-card trace-card--error">
      <p class="eyebrow">{{ t('agentTrace.eventTypes.error') }} ({{ t('agentTrace.step') }} {{ err.step }})</p>
      <pre class="trace-error-text">{{ err.data?.error || '-' }}</pre>
    </div>

    <!-- Finish event -->
    <div v-if="finishEvent" class="trace-card trace-card--finish">
      <p class="eyebrow">{{ t('agentTrace.eventTypes.finish') }}</p>
      <div class="inline-meta">
        <span>{{ t('agentTrace.finalStatus') }}: {{ finishEvent.data?.status || '-' }}</span>
        <span v-if="finishEvent.data?.reason">{{ t('agentTrace.reason') }}: {{ finishEvent.data.reason }}</span>
      </div>
    </div>

    <!-- Summary card -->
    <div v-if="summaryEvent" class="trace-card trace-card--summary">
      <p class="eyebrow">{{ t('agentTrace.eventTypes.summary') }}</p>
      <div class="inline-meta">
        <span>{{ t('agentTrace.runId') }}: {{ summaryEvent.run_id || '-' }}</span>
        <span>{{ t('agentTrace.finalStatus') }}: {{ summaryEvent.status || '-' }}</span>
        <span>{{ t('agentTrace.totalSteps') }}: {{ summaryEvent.steps ?? '-' }}</span>
        <span v-if="summaryEvent.test_case_id">{{ t('agentTrace.testCaseId') }}: {{ summaryEvent.test_case_id }}</span>
        <span v-if="summaryEvent.execution_id">{{ t('agentTrace.executionId') }}: {{ summaryEvent.execution_id }}</span>
      </div>
      <p v-if="summaryEvent.error" class="trace-error-text">{{ summaryEvent.error }}</p>
    </div>

    <!-- Empty state -->
    <div v-if="!hasEvents && !running" class="mono-empty">
      {{ t('agentTrace.empty') }}
    </div>

    <!-- Loading state -->
    <div v-if="running && !hasEvents" class="mono-empty">
      {{ t('agentTrace.waiting') }}
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { storeToRefs } from 'pinia'

import { useI18n } from '../i18n'
import { useAgentStore } from '../stores/agent.js'
import {
  resolveAgentStatusTagType,
  formatEventTime,
  truncateText,
} from '../view-models/agent-trace.js'

const { t } = useI18n()
const agentStore = useAgentStore()
const scrollContainer = ref(null)

watch(
  () => agentStore.events.length,
  async () => {
    await nextTick()
    if (scrollContainer.value) {
      scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
    }
  }
)
const emit = defineEmits(['clear'])

const {
  events,
  running,
  agentStatus,
  hasEvents,
} = storeToRefs(agentStore)

const taskAnalysis = computed(() => agentStore.taskAnalysis)
const plan = computed(() => agentStore.plan)
const stepPairs = computed(() => agentStore.stepPairs)
const errorEvents = computed(() => agentStore.errorEvents)
const finishEvent = computed(() => agentStore.finishEvent)
const summaryEvent = computed(() => agentStore.summary)
const statusTagType = computed(() => resolveAgentStatusTagType(agentStatus.value))

const completedPlanSteps = computed(() => {
  return new Set(
    agentStore.planStepEvents
      .filter((e) => e.data?.status === 'completed')
      .map((e) => e.data?.step_number)
  )
})

const planStepStatus = (stepNumber) => {
  return completedPlanSteps.value.has(stepNumber) ? 'success' : ''
}

const planStepsForStep = (agentStep) => {
  return agentStore.planStepEvents.filter((e) => e.step === agentStep)
}
</script>

<style scoped>
.agent-trace-panel {
  max-height: 720px;
  overflow-y: auto;
}

.agent-trace-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pulse-tag {
  animation: pulse 1.2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.trace-card {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.72);
  margin-bottom: 12px;
}

.trace-card--analysis {
  border-left: 3px solid var(--accent);
}

.trace-card--plan {
  border-left: 3px solid var(--accent);
}

.trace-card--error {
  border-left: 3px solid var(--danger);
  background: rgba(216, 77, 77, 0.04);
}

.trace-card--finish {
  border-left: 3px solid var(--success);
}

.trace-card--summary {
  border-left: 3px solid var(--accent);
  background: var(--accent-soft);
}

.trace-steps-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 10px;
}

.trace-step-chip {
  font-size: 13px;
  color: var(--ink-soft);
}

.trace-plan-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.trace-plan-desc {
  flex: 1;
}

.trace-timeline {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.trace-step-group {
  border-left: 2px solid var(--line);
  margin-left: 16px;
  padding-left: 0;
  animation: fadeInUp 0.3s ease both;
}

.trace-step-group--active {
  border-left-color: var(--accent);
  background: linear-gradient(90deg, rgba(64, 158, 255, 0.06) 0%, transparent 100%);
  border-radius: 0 8px 8px 0;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.trace-row {
  display: flex;
  gap: 10px;
  padding: 8px 0 8px 14px;
}

.trace-step-num {
  min-width: 28px;
  font-weight: 700;
  font-size: 14px;
  color: var(--accent);
  text-align: center;
  padding-top: 2px;
}

.trace-row-body {
  flex: 1;
  min-width: 0;
}

.trace-row-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.trace-thought {
  margin: 4px 0;
  font-size: 14px;
  line-height: 1.5;
}

.trace-action-label {
  font-size: 12px;
  color: var(--ink-soft);
  font-weight: 600;
}

.trace-observation {
  margin: 6px 0 0;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f7f9fc;
  color: #1e2a3f;
  font-size: 12px;
  line-height: 1.5;
  font-family: 'Cascadia Code', Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 160px;
  overflow-y: auto;
  border: 1px solid rgba(23, 32, 51, 0.06);
}

.trace-error-text {
  margin: 6px 0 0;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(216, 77, 77, 0.06);
  color: var(--danger);
  font-size: 12px;
  font-family: 'Cascadia Code', Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
