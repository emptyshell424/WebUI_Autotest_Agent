<template>
  <div class="view-grid settings-grid">
    <section class="surface-panel">
      <div class="section-title">
        <div>
          <h4>{{ t('settings.connectionTitle') }}</h4>
          <p class="section-hint">{{ t('settings.connectionHint') }}</p>
        </div>
      </div>

      <div class="settings-form">
        <el-input v-model="apiBaseUrlDraft" placeholder="http://127.0.0.1:8000/api/v1">
          <template #prepend>{{ t('common.api') }}</template>
        </el-input>

        <div class="toolbar-row">
          <el-button type="primary" @click="saveApiUrl">{{ t('common.saveAndReload') }}</el-button>
          <el-button @click="resetApiUrl">{{ t('common.resetDefault') }}</el-button>
          <el-button text :loading="appStore.loadingHealth" @click="refreshHealth">{{ t('common.refreshHealth') }}</el-button>
        </div>

        <p class="muted">{{ t('settings.currentApiBaseUrl', { value: appStore.apiBaseUrl }) }}</p>
      </div>
    </section>

    <section class="surface-panel --solid">
      <div class="section-title">
        <div>
          <h4>{{ t('settings.snapshotTitle') }}</h4>
          <p class="section-hint">{{ t('settings.snapshotHint') }}</p>
        </div>
        <el-button
          :loading="appStore.rebuildingKnowledge"
          @click="rebuildKnowledge"
          :disabled="appStore.loadingHealth"
        >
          {{ t('settings.rebuildKnowledge') }}
        </el-button>
      </div>

      <div class="detail-grid">
        <article v-for="section in sections" :key="section.key" class="detail-block">
          <div class="section-title --compact">
            <div>
              <p class="eyebrow">{{ section.key }}</p>
              <h4>{{ section.title }}</h4>
            </div>
            <span class="status-badge" :data-state="section.status">{{ section.status }}</span>
          </div>
          <dl class="kv-list">
            <template v-for="[label, value] in section.entries" :key="label">
              <dt>{{ label }}</dt>
              <dd>{{ value }}</dd>
            </template>
          </dl>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { useI18n } from '../i18n'
import { useAppStore } from '../stores/app'

const appStore = useAppStore()
const { t } = useI18n()
const apiBaseUrlDraft = ref(appStore.apiBaseUrl)

watch(
  () => appStore.apiBaseUrl,
  (value) => {
    apiBaseUrlDraft.value = value
  }
)

const sections = computed(() => {
  if (!appStore.health) {
    return []
  }

  return [
    {
      key: t('common.healthBackend'),
      title: t('settings.apiService'),
      status: appStore.health.backend.status,
      entries: Object.entries(appStore.health.backend.details || {}),
    },
    {
      key: t('common.healthModel'),
      title: t('settings.llmRuntime'),
      status: appStore.health.model.status,
      entries: Object.entries(appStore.health.model.details || {}),
    },
    {
      key: t('common.healthKnowledge'),
      title: t('settings.knowledgeBase'),
      status: appStore.health.knowledge_base.status,
      entries: Object.entries(appStore.health.knowledge_base.details || {}),
    },
    {
      key: t('common.healthStorage'),
      title: t('settings.localRuntime'),
      status: appStore.health.storage.status,
      entries: Object.entries(appStore.health.storage.details || {}),
    },
  ]
})

const refreshHealth = async () => {
  try {
    await appStore.fetchHealth()
    ElMessage.success(t('settings.healthRefreshed'))
  } catch (error) {
    ElMessage.error(appStore.healthError || t('settings.healthRefreshFailed'))
  }
}

const saveApiUrl = async () => {
  appStore.saveApiBaseUrl(apiBaseUrlDraft.value)
  await refreshHealth()
}

const resetApiUrl = async () => {
  appStore.restoreDefaultApiBaseUrl()
  await refreshHealth()
}

const rebuildKnowledge = async () => {
  try {
    await appStore.rebuildKnowledge()
    ElMessage.success(t('settings.knowledgeRebuilt'))
  } catch (error) {
    ElMessage.error(appStore.healthError || t('settings.knowledgeRebuildFailed'))
  }
}
</script>
