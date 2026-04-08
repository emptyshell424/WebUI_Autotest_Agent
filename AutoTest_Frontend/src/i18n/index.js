import { computed, ref } from 'vue'

const LOCALE_STORAGE_KEY = 'autotest-locale'
const SUPPORTED_LOCALES = new Set(['en', 'zh-CN'])

const messages = {
  en: {
    common: {
      refresh: 'Refresh',
      refreshHistory: 'Refresh history',
      refreshMetrics: 'Refresh metrics',
      refreshHealth: 'Refresh health',
      saveAndReload: 'Save and reload',
      resetDefault: 'Reset default',
      inspect: 'Inspect',
      pending: 'Pending',
      running: 'Running',
      notTriggered: 'Not triggered',
      noRepairSummary: 'No repair summary captured.',
      noRepairedCode: '(no repaired code saved)',
      noStdout: '(no stdout captured)',
      noStderr: '(no stderr captured)',
      online: 'Online',
      offline: 'Offline',
      indexed: 'Indexed',
      notCreated: 'Not created',
      selectedExecution: 'Selected execution',
      healthBackend: 'Backend',
      healthModel: 'Model',
      healthKnowledge: 'Knowledge',
      healthStorage: 'Storage',
      api: 'API',
    },
    app: {
      project: 'Graduation Project',
      product: 'AutoTest Agent',
      productSubtitle:
        'Natural-language driven web automation workspace for generation, execution, and review.',
      navWorkbench: 'Workbench',
      navHistory: 'History',
      navMetrics: 'Metrics',
      navSettings: 'Settings',
      platform: 'AutoTest Agent Platform',
      pageWorkbench: 'Scenario generation and execution workspace',
      pageHistory: 'Execution history and replay',
      pageMetrics: 'Execution metrics and experiment summary',
      pageSettings: 'System settings and health',
      systemHealthy: 'System healthy',
      needsAttention: 'Needs attention',
      backendLabel: 'Backend',
      knowledgeLabel: 'Knowledge',
      knowledgePending: 'Pending',
      errorDescription:
        'Check the backend service, API base URL, or model configuration and try again.',
      language: 'Language',
      languageEnglish: 'EN',
      languageChinese: '中文',
    },
    workbench: {
      currentStatus: 'Current status',
      knowledgeHits: 'Knowledge hits',
      latestCase: 'Latest case',
      repairAttempts: 'Repair attempts',
      sectionTitle: 'Scenario brief',
      sectionHint:
        'Describe the target website, user action, expected assertion, and any waiting or login details.',
      promptPlaceholder:
        'For example: open the login page, enter credentials, click sign in, then verify the welcome message appears.',
      autoRun: 'Generate + Run',
      generateOnly: 'Generate only',
      generateScript: 'Generate script',
      runCurrentScript: 'Run current script',
      refreshExecution: 'Refresh execution',
      knowledgeContext: 'Knowledge context',
      generatedScript: 'Generated script',
      generatedHint: 'You can adjust the script before launching a new execution.',
      repairSummary: 'Repair summary',
      attempt: 'Attempt {count}',
      repairRetryFallback: 'The system retried this case after a failed run.',
      editorPlaceholder: 'Generate a test case to populate this editor.',
      executionTrace: 'Execution trace',
      executionTraceHint: 'Logs, validation blockers, and runtime errors land here.',
      execution: 'Execution',
      started: 'Started',
      finished: 'Finished',
      healing: 'Healing',
      repairAttemptsCount: '{count} attempt(s)',
      repairTimeline: 'Repair timeline',
      repairTimelineHint:
        'Inspect the failure reason, repair summary, and repaired code for each retry.',
      emptyTrace: 'Start a run to see the live execution trace and runtime logs here.',
      generatedAndStarted: 'Script generated and execution started.',
      generated: 'Script generated.',
      generationFailed: 'Script generation failed.',
      executionCreated: 'Execution created. Polling for updates.',
      executionCreateFailed: 'Failed to create the execution.',
      executionRefreshed: 'Execution status refreshed.',
      executionRefreshFailed: 'Failed to refresh execution status.',
      status: {
        idle: 'Idle',
        generated: 'Generated',
        queued: 'Queued',
        running: 'Running',
        completed: 'Completed',
        healed_completed: 'Healed and completed',
        healed_failed: 'Repair attempted but failed',
        failed: 'Failed',
        blocked: 'Blocked',
      },
    },
    history: {
      title: 'Execution history',
      hint: 'Review recent runs, compare outcomes, and reopen details.',
      empty: 'No execution history yet',
      status: 'Status',
      outcome: 'Outcome',
      scenario: 'Scenario',
      repairs: 'Repairs',
      createdAt: 'Created at',
      finishedAt: 'Finished at',
      actions: 'Actions',
      selectedHint: 'Inspect the exact script, runtime output, and validation blockers.',
      openInWorkbench: 'Open in workbench',
      case: 'Case',
      executedScript: 'Executed script',
      logs: 'Logs',
      repairAttempt: 'Repair attempt {count}',
      selectToInspect: 'Select an execution to inspect its details.',
      historyRefreshed: 'Execution history refreshed.',
      historyRefreshFailed: 'Failed to refresh execution history.',
      loadExecutionFailed: 'Failed to load execution details.',
      outcomeFirstPass: 'First-pass success',
      outcomeRepairSuccess: 'Repair success',
      outcomeRepairFailed: 'Repair failed',
      outcomeBlocked: 'Blocked by safety rules',
      outcomeRunFailed: 'Run failed',
    },
    metrics: {
      title: 'Execution metrics',
      hint: 'Use these indicators for your thesis experiments, demo summary, and resume bullet points.',
      empty: 'Run a few executions to build your experiment summary.',
      refreshed: 'Execution metrics refreshed.',
      refreshFailed: 'Failed to refresh execution metrics.',
      groups: {
        volume: 'Volume',
        success: 'Success',
        healing: 'Healing',
        outcome: 'Outcome',
      },
      labels: {
        generatedCases: 'Generated test cases',
        executionRecords: 'Execution records',
        firstPassSuccessRate: 'First-pass success rate',
        selfHealTriggeredRate: 'Self-heal triggered rate',
        selfHealSuccessRate: 'Self-heal success rate',
        finalSuccessRate: 'Final success rate',
      },
    },
    settings: {
      connectionTitle: 'Connection and defaults',
      connectionHint:
        'Use a local backend by default, then override it when you need a different environment.',
      currentApiBaseUrl: 'Current API base URL: {value}',
      snapshotTitle: 'Backend health snapshot',
      snapshotHint: 'Model availability, knowledge indexing, and runtime storage are summarized here.',
      rebuildKnowledge: 'Rebuild knowledge base',
      apiService: 'API service',
      llmRuntime: 'LLM runtime',
      knowledgeBase: 'Knowledge base',
      localRuntime: 'Local runtime',
      healthRefreshed: 'Backend health refreshed.',
      healthRefreshFailed: 'Failed to refresh backend health.',
      knowledgeRebuilt: 'Knowledge base rebuilt.',
      knowledgeRebuildFailed: 'Failed to rebuild the knowledge base.',
    },
  },
  'zh-CN': {
    common: {
      refresh: '刷新',
      refreshHistory: '刷新历史',
      refreshMetrics: '刷新指标',
      refreshHealth: '刷新健康状态',
      saveAndReload: '保存并重新加载',
      resetDefault: '恢复默认',
      inspect: '查看',
      pending: '待处理',
      running: '运行中',
      notTriggered: '未触发',
      noRepairSummary: '暂无修复摘要。',
      noRepairedCode: '（未保存修复后的代码）',
      noStdout: '（未捕获 stdout）',
      noStderr: '（未捕获 stderr）',
      online: '在线',
      offline: '离线',
      indexed: '已索引',
      notCreated: '未创建',
      selectedExecution: '已选执行记录',
      healthBackend: '后端',
      healthModel: '模型',
      healthKnowledge: '知识库',
      healthStorage: '存储',
      api: '接口',
    },
    app: {
      project: '毕业设计',
      product: 'AutoTest Agent',
      productSubtitle: '一个通过自然语言完成生成、执行和回溯的 Web 自动化工作台。',
      navWorkbench: '工作台',
      navHistory: '历史记录',
      navMetrics: '指标统计',
      navSettings: '系统设置',
      platform: 'AutoTest Agent 平台',
      pageWorkbench: '场景生成与执行工作台',
      pageHistory: '执行历史与回放',
      pageMetrics: '执行指标与实验汇总',
      pageSettings: '系统设置与健康状态',
      systemHealthy: '系统健康',
      needsAttention: '需要关注',
      backendLabel: '后端',
      knowledgeLabel: '知识库',
      knowledgePending: '待处理',
      errorDescription: '请检查后端服务、API 地址或模型配置后再试。',
      language: '语言',
      languageEnglish: 'EN',
      languageChinese: '中文',
    },
    workbench: {
      currentStatus: '当前状态',
      knowledgeHits: '知识命中数',
      latestCase: '最新用例',
      repairAttempts: '修复次数',
      sectionTitle: '场景描述',
      sectionHint: '描述目标网站、用户操作、预期断言，以及等待或登录等细节。',
      promptPlaceholder: '例如：打开登录页，输入账号密码，点击登录，然后验证欢迎语出现。',
      autoRun: '生成并运行',
      generateOnly: '仅生成',
      generateScript: '生成脚本',
      runCurrentScript: '运行当前脚本',
      refreshExecution: '刷新执行状态',
      knowledgeContext: '知识上下文',
      generatedScript: '生成脚本',
      generatedHint: '在发起新一轮执行前，你可以先调整脚本。',
      repairSummary: '修复摘要',
      attempt: '第 {count} 次尝试',
      repairRetryFallback: '系统在运行失败后对该用例进行了重试。',
      editorPlaceholder: '先生成一个测试用例来填充这里的编辑器。',
      executionTrace: '执行轨迹',
      executionTraceHint: '日志、校验阻塞项和运行时错误会显示在这里。',
      execution: '执行记录',
      started: '开始时间',
      finished: '结束时间',
      healing: '自愈',
      repairAttemptsCount: '{count} 次尝试',
      repairTimeline: '修复时间线',
      repairTimelineHint: '查看每次重试的失败原因、修复摘要和修复后代码。',
      emptyTrace: '开始一次运行后，这里会显示实时执行轨迹和运行日志。',
      generatedAndStarted: '脚本已生成，并已启动执行。',
      generated: '脚本已生成。',
      generationFailed: '脚本生成失败。',
      executionCreated: '执行任务已创建，正在轮询状态。',
      executionCreateFailed: '创建执行任务失败。',
      executionRefreshed: '执行状态已刷新。',
      executionRefreshFailed: '刷新执行状态失败。',
      status: {
        idle: '空闲',
        generated: '已生成',
        queued: '排队中',
        running: '运行中',
        completed: '已完成',
        healed_completed: '修复后完成',
        healed_failed: '已尝试修复但失败',
        failed: '失败',
        blocked: '被阻止',
      },
    },
    history: {
      title: '执行历史',
      hint: '查看最近运行结果，对比结果，并重新打开详情。',
      empty: '暂无执行历史',
      status: '状态',
      outcome: '结果',
      scenario: '场景',
      repairs: '修复次数',
      createdAt: '创建时间',
      finishedAt: '结束时间',
      actions: '操作',
      selectedHint: '查看精确脚本、运行输出和校验阻塞项。',
      openInWorkbench: '在工作台中打开',
      case: '用例',
      executedScript: '执行脚本',
      logs: '日志',
      repairAttempt: '第 {count} 次修复',
      selectToInspect: '请选择一条执行记录查看详情。',
      historyRefreshed: '执行历史已刷新。',
      historyRefreshFailed: '刷新执行历史失败。',
      loadExecutionFailed: '加载执行详情失败。',
      outcomeFirstPass: '首次通过',
      outcomeRepairSuccess: '修复成功',
      outcomeRepairFailed: '修复失败',
      outcomeBlocked: '被安全规则阻止',
      outcomeRunFailed: '运行失败',
    },
    metrics: {
      title: '执行指标',
      hint: '这些指标可以直接用于论文实验、演示总结和简历亮点。',
      empty: '先运行几次执行任务，这里才会形成实验汇总。',
      refreshed: '执行指标已刷新。',
      refreshFailed: '刷新执行指标失败。',
      groups: {
        volume: '规模',
        success: '成功',
        healing: '自愈',
        outcome: '结果',
      },
      labels: {
        generatedCases: '生成的测试用例数',
        executionRecords: '执行记录数',
        firstPassSuccessRate: '首次成功率',
        selfHealTriggeredRate: '触发自愈比例',
        selfHealSuccessRate: '自愈成功率',
        finalSuccessRate: '最终成功率',
      },
    },
    settings: {
      connectionTitle: '连接与默认值',
      connectionHint: '默认使用本地后端；需要切换环境时，可以在这里覆盖。',
      currentApiBaseUrl: '当前 API 地址：{value}',
      snapshotTitle: '后端健康快照',
      snapshotHint: '这里汇总展示模型可用性、知识索引和运行时存储状态。',
      rebuildKnowledge: '重建知识库',
      apiService: 'API 服务',
      llmRuntime: 'LLM 运行时',
      knowledgeBase: '知识库',
      localRuntime: '本地运行时',
      healthRefreshed: '后端健康状态已刷新。',
      healthRefreshFailed: '刷新后端健康状态失败。',
      knowledgeRebuilt: '知识库已重建。',
      knowledgeRebuildFailed: '重建知识库失败。',
    },
  },
}

const getInitialLocale = () => {
  if (typeof window === 'undefined') {
    return 'en'
  }
  const savedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY)
  if (savedLocale && SUPPORTED_LOCALES.has(savedLocale)) {
    return savedLocale
  }
  const browserLocale = window.navigator.language?.toLowerCase() || ''
  return browserLocale.startsWith('zh') ? 'zh-CN' : 'en'
}

export const locale = ref(getInitialLocale())

export const setLocale = (nextLocale) => {
  if (!SUPPORTED_LOCALES.has(nextLocale)) {
    return
  }
  locale.value = nextLocale
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, nextLocale)
  }
}

const formatMessage = (template, params = {}) =>
  template.replace(/\{(\w+)\}/g, (_, key) => `${params[key] ?? ''}`)

export const translate = (path, params = {}) => {
  const scopes = path.split('.')
  let current = messages[locale.value] || messages.en

  for (const scope of scopes) {
    current = current?.[scope]
  }

  if (typeof current !== 'string') {
    current = scopes.reduce((value, scope) => value?.[scope], messages.en)
  }

  if (typeof current !== 'string') {
    return path
  }

  return formatMessage(current, params)
}

export const useI18n = () => ({
  locale: computed(() => locale.value),
  setLocale,
  t: (path, params) => translate(path, params),
})
