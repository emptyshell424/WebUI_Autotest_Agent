<template>
  <div class="app-shell">
    <aside class="app-rail">
      <div class="brand-block">
        <p class="eyebrow">{{ t('app.project') }}</p>
        <h1>{{ t('app.product') }}</h1>
        <p class="brand-copy">{{ t('app.productSubtitle') }}</p>
      </div>

      <el-menu
        :default-active="route.path"
        router
        class="app-nav"
        background-color="transparent"
        text-color="var(--ink-soft)"
        active-text-color="var(--accent)"
      >
        <el-menu-item index="/">
          <el-icon><Monitor /></el-icon>
          <span>{{ t('app.navWorkbench') }}</span>
        </el-menu-item>
        <el-menu-item index="/history">
          <el-icon><Tickets /></el-icon>
          <span>{{ t('app.navHistory') }}</span>
        </el-menu-item>
        <el-menu-item index="/metrics">
          <el-icon><DataAnalysis /></el-icon>
          <span>{{ t('app.navMetrics') }}</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>{{ t('app.navSettings') }}</span>
        </el-menu-item>
      </el-menu>

      <div class="rail-footer">
        <div class="status-line">
          <span>{{ t('app.backendLabel') }}</span>
          <strong :class="appStore.backendConnected ? 'is-success' : 'is-danger'">
            {{ appStore.backendConnected ? t('common.online') : t('common.offline') }}
          </strong>
        </div>
        <div class="status-line">
          <span>{{ t('app.knowledgeLabel') }}</span>
          <strong :class="appStore.knowledgeReady ? 'is-success' : 'is-warning'">
            {{ appStore.knowledgeReady ? t('common.indexed') : t('app.knowledgePending') }}
          </strong>
        </div>
      </div>
    </aside>

    <main class="app-main">
      <header class="topbar">
        <div>
          <p class="eyebrow">{{ t('app.platform') }}</p>
          <h2>{{ pageMeta.title }}</h2>
        </div>
        <div class="topbar-actions">
          <el-segmented
            :model-value="locale"
            :options="localeOptions"
            size="default"
            @change="setLocale"
          />
          <div class="health-pill" :data-state="appStore.overallStatus">
            <span class="health-dot"></span>
            <span>
              {{ appStore.overallStatus === 'healthy' ? t('app.systemHealthy') : t('app.needsAttention') }}
            </span>
          </div>
          <el-button text @click="refreshHealth" :loading="appStore.loadingHealth">{{ t('common.refresh') }}</el-button>
        </div>
      </header>

      <section v-if="appStore.healthError" class="shell-alert">
        <el-alert
          type="error"
          :closable="false"
          :title="appStore.healthError"
          :description="t('app.errorDescription')"
          show-icon
        />
      </section>

      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { DataAnalysis, Monitor, Setting, Tickets } from '@element-plus/icons-vue'

import { useAppStore } from './stores/app'
import { useI18n } from './i18n'
import { useWorkspaceStore } from './stores/workspace'

const route = useRoute()
const appStore = useAppStore()
const workspaceStore = useWorkspaceStore()
const { locale, setLocale, t } = useI18n()

const localeOptions = computed(() => [
  {
    label: t('app.languageEnglish'),
    value: 'en',
  },
  {
    label: t('app.languageChinese'),
    value: 'zh-CN',
  },
])

const pageMeta = computed(() => {
  if (route.path === '/history') {
    return {
      title: t('app.pageHistory'),
    }
  }
  if (route.path === '/settings') {
    return {
      title: t('app.pageSettings'),
    }
  }
  if (route.path === '/metrics') {
    return {
      title: t('app.pageMetrics'),
    }
  }
  return {
    title: t('app.pageWorkbench'),
  }
})

const refreshHealth = async () => {
  try {
    await appStore.fetchHealth()
  } catch (error) {
    console.error(error)
  }
}

onMounted(async () => {
  appStore.bootstrap()
  try {
    await Promise.all([
      appStore.fetchHealth(),
      appStore.fetchStats(),
      appStore.fetchRuntimeSettings(),
      workspaceStore.fetchHistory(),
    ])
  } catch (error) {
    console.error(error)
  }
})
</script>
