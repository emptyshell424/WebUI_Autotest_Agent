# WebUI AutoTest Agent — 优化审计与下一步规划

> 审计时间：2026-04-23
> 审计范围：全仓库（后端服务、前端界面、测试体系、CI、文档、知识库）

---

## 执行进度

> 最后更新：2026-04-23

| 阶段 | 状态 | 完成项 |
| ---- | ---- | ------ |
| **A：工程质量收口** | ✅ 完成 | 后端日志体系 (2.2)、清理 run-build.mjs (2.3)、修复静默 pass (2.5)、Settings 表单标签 (3.2)、API Client 拦截器 (3.4) |
| **B：测试与验证加固** | ✅ 完成 | 引入 Vitest (3.1)、后端 API 集成测试 (4.1 — 15 个测试)、前端组件测试 (4.2 — SettingsView + WorkbenchView)、RAG 检索质量验证 (5.2 — 6 个质量测试) |
| **C：知识库与实验数据** | ⚠️ 部分完成 | 扩充知识库 3 份新文档 (5.1)；C-2/C-3/C-4 需要 LLM API Key + 浏览器环境，待手工执行 |
| **D：展示层与文档收口** | ✅ 完成 | Metrics 趋势图表 (3.7)、CodeEditor 组件 (3.6)、根目录 README (6.3)、架构文档 ARCHITECTURE.md |

**验证结果**：

- 后端：62 个测试全部通过 (`python run_backend_tests.py`)
- 前端：8 个测试文件、18 个测试全部通过 (`npm test`)
- 前端构建：成功 (`npm run build`)

---

## 一、总体评估

项目核心闭环（自然语言 → RAG 检索 → 脚本生成 → 本地执行 → 自愈修复 → 历史与指标展示）已基本成型，架构分层清晰（FastAPI + Vue 3 + Element Plus + Pinia），代码风格统一。

**当前主要短板集中在三个层面：**

1. **工程健壮性**：部分模块存在代码重复、缺少日志/监控、连接管理不够精细
2. **测试与可验证性**：前端测试仅覆盖纯逻辑层，后端测试缺少集成级覆盖
3. **实验证据**：手工实验场景全部 Pending，缺少可复现的截图和对比数据

---

## 二、后端优化点

### 2.1 数据库连接管理 — 每次操作都重新建连接

**位置**：`AutoTest_Backend/app/core/database.py` → `get_connection()`

**现状**：每次调用 `get_connection()` 都会执行 `sqlite3.connect()` → `commit()` → `close()`，无连接池。`ExecutionRepository` 中的 `get()`、`mark_running()`、`mark_finished()` 等方法各自独立获取连接，一次执行流程可能产生 10+ 次连接建开销。

**建议**：
- 引入轻量级连接池或使用单例连接（SQLite 单写者模型下单连接即可）
- 将 `ExecutionService._run_execution_inner()` 中的多步数据库操作合并为事务
- 优先级：**P2**（当前并发低，非阻塞瓶颈）

### 2.2 日志体系缺失

**位置**：全后端服务层

**现状**：整个后端没有使用 Python `logging` 模块。`execution_service.py` 中捕获异常后直接 `pass`（第 217-218 行），`rag_service.py` 中 `_reset_collection` 吞掉异常。无法追踪生产环境下的问题根因。

**建议**：
- 在 `app/core/` 下新增 `logger.py`，统一配置 `logging`
- 关键节点必须记录日志：LLM 请求/响应、脚本执行启停、自愈触发、RAG 检索结果
- 异常捕获点（`except Exception: pass`）必须至少 `logger.exception()`
- 优先级：**P1**

### 2.3 `run-build.mjs` 构建脚本与 `vite.config.js` 功能重复

**位置**：
- `AutoTest_Frontend/scripts/run-build.mjs`
- `AutoTest_Frontend/vite.config.js`

**现状**：`run-build.mjs` 中的 `manualChunks` 配置与 `vite.config.js` 完全相同，且 `run-build.mjs` 设置了 `configFile: false` 绕过标准配置、`esbuild: false` 禁用 esbuild。这导致构建行为与开发行为不一致。`package.json` 的 `build` 已改为 `vite build`，但 `run-build.mjs` 仍然残留。

**建议**：
- 删除 `run-build.mjs`，统一使用 `vite build` + `vite.config.js`
- 如果需要自定义构建逻辑，在 `vite.config.js` 中通过插件实现
- 优先级：**P1**（残留文件造成混淆）

### 2.4 `_normalize` 和 `_contains_any` 方法重复定义

**位置**：
- `AutoTest_Backend/app/services/generation_service.py` 第 170-174 行
- `AutoTest_Backend/app/services/strategy_service.py` 第 241-245 行

**现状**：两个服务各自定义了完全相同的 `_normalize()` 和 `_contains_any()` 方法。

**建议**：
- 提取到 `app/utils/text_helpers.py` 作为公共函数
- 优先级：**P2**

### 2.5 `ExecutionService._run_execution` 异常处理中的静默 pass

**位置**：`AutoTest_Backend/app/services/execution_service.py` 第 209-218 行

```python
except Exception as exc:
    try:
        self.execution_repository.mark_finished(...)
        self.test_case_repository.update_status(...)
    except Exception:
        pass  # ← 完全吞掉异常
```

**现状**：如果 `mark_finished` 本身也失败（例如数据库锁），错误会被完全吞掉，执行记录永远停留在 `running` 状态。

**建议**：
- 至少 `logger.exception("Failed to mark execution as failed")` 记录日志
- 考虑添加 fallback 状态恢复机制
- 优先级：**P1**

### 2.6 `container.py` 中持久化设置写入时机不当

**位置**：`AutoTest_Backend/app/core/container.py` 第 59-67 行

**现状**：每次创建容器都会把 `knowledge_base_dir` 和 `model_name` 写入 `system_setting` 表，但 Settings 路由中已清理了这两个字段的暴露（只暴露 3 个可配字段）。这里的写入变成了无意义的数据冗余。

**建议**：
- 移除 `knowledge_base_dir` 和 `model_name` 的 `upsert_many` 调用，只持久化真正可配的 3 个字段
- 优先级：**P2**

### 2.7 `rag_service.py` 体量过大

**位置**：`AutoTest_Backend/app/services/rag_service.py`（576 行）

**现状**：单个文件包含了词表别名（100 行）、查询扩展逻辑、BM25 实现、向量检索、hybrid 合并、rerank 排序、知识库重建等全部 RAG 逻辑。

**建议**：
- 将 `TERM_ALIASES` / `CANONICAL_EXPANSIONS` 拆到 `app/core/rag_vocabulary.py`
- 将 BM25 实现拆到 `app/services/bm25.py`
- 保持 `RAGService` 作为编排层
- 优先级：**P2**

### 2.8 代码安全校验白名单过于宽泛

**位置**：`AutoTest_Backend/app/services/execution_service.py` 第 33-44 行

**现状**：`SAFE_IMPORTS` 包含 `urllib`，但 `BLOCKED_CALLS` 没有拦截 `urllib.request.urlopen` 等可能的网络调用。`BLOCKED_PREFIXES` 只拦截了 `os.` 但没拦截 `os` 模块的间接使用。

**建议**：
- 考虑更细粒度的 `urllib` 模块控制（只允许 `urllib.parse`）
- 添加网络相关调用的检测（`urlopen`, `Request` 等）
- 优先级：**P2**

---

## 三、前端优化点

### 3.1 缺少前端测试框架（Vitest / @vue/test-utils）

**位置**：`AutoTest_Frontend/scripts/run-tests.mjs`

**现状**：前端测试使用自写的 Node 脚本 + `node:assert/strict` 手动模拟，无法测试 Vue 组件挂载、DOM 交互。所有 `.test.js` 文件都是纯函数测试，无组件级覆盖。

**建议**：
- 引入 `vitest` + `@vue/test-utils` + `happy-dom`
- 为 Settings / Workbench 页编写组件挂载测试
- 优先级：**P1**

### 3.2 Settings 页表单缺少字段标签

**位置**：`AutoTest_Frontend/src/views/SettingsView.vue` 第 43-45 行

**现状**：三个 `el-input-number` 组件没有 `<el-form-item label="...">` 包裹，用户无法知道每个数字输入框对应什么配置项。

**建议**：
- 使用 `el-form` + `el-form-item` 包裹，添加标签文案
- 添加 i18n key 支持中英文标签
- 优先级：**P1**（影响可用性和演示观感）

### 3.3 前端无全局错误边界

**位置**：`AutoTest_Frontend/src/App.vue`

**现状**：`onMounted` 中的 `Promise.all` 如果部分请求失败，只是 `console.error`。没有使用 Vue 的 `app.config.errorHandler` 或 `<ErrorBoundary>` 组件。未捕获的 Promise rejection 会导致白屏。

**建议**：
- 在 `main.js` 中配置 `app.config.errorHandler`
- 添加全局错误提示（`ElMessage.error`）
- 优先级：**P2**

### 3.4 API Client 缺少请求/响应拦截器

**位置**：`AutoTest_Frontend/src/api/client.js`

**现状**：`apiClient` 创建后没有配置拦截器。没有统一的 401/403/500 错误处理，没有请求超时重试。初始化时 `baseURL` 未设置，依赖后续调用 `setApiBaseUrl`。

**建议**：
- 添加响应拦截器统一处理 HTTP 错误码
- 在创建 `apiClient` 时设置 `baseURL`（当前靠 `App.vue` 的 `bootstrap` 延迟设置）
- 优先级：**P1**

### 3.5 i18n 实现未使用 computed 翻译

**位置**：`AutoTest_Frontend/src/i18n/index.js`

**现状**：`useI18n()` 返回的 `t` 是普通函数而非 computed。当 `locale` 切换时，已渲染的非模板内文案（例如在 `<script setup>` 中缓存的字符串）不会自动更新。

**建议**：
- 当前实现在模板中使用 `t()` 是响应式的（因为模板重新渲染），但 `<script>` 中的调用不响应
- 如需严格响应式，可用 `vue-i18n` 替换，或在 `computed` 中调用 `t()`
- 优先级：**P3**（当前场景影响不大）

### 3.6 `WorkbenchView.vue` 代码编辑区使用 `<textarea>`

**位置**：`AutoTest_Frontend/src/views/WorkbenchView.vue`

**现状**：生成的 Python 脚本在一个普通 `<textarea>` 或 `<el-input type="textarea">` 中展示，无语法高亮、行号、代码折叠。

**建议**：
- 引入轻量级代码编辑器（如 `codemirror` 或 `monaco-editor`）
- 至少支持 Python 语法高亮和行号显示
- 优先级：**P2**（提升演示观感）

### 3.7 Metrics 页缺少可视化图表

**位置**：`AutoTest_Frontend/src/views/MetricsView.vue`

**现状**：指标数据只有数字卡片 + `el-table` 趋势表格，没有折线图、柱状图等可视化。

**建议**：
- 引入 `echarts` 或 `chart.js`，为趋势数据添加折线图
- 为成功率/自愈率添加饼图或环形图
- 优先级：**P2**（毕设答辩中图表比数字更有说服力）

---

## 四、测试体系优化点

### 4.1 后端缺少 API 集成测试

**位置**：`AutoTest_Backend/tests/`

**现状**：10 个测试文件、30 个用例，但多数是单元级测试（mock LLM、mock 数据库）。缺少使用 `TestClient` 的端到端 API 集成测试。

**建议**：
- 使用 FastAPI 的 `TestClient` 编写核心链路集成测试
- 至少覆盖：`POST /generate` → `POST /executions` → `GET /executions/{id}` → `GET /executions/stats`
- 优先级：**P1**

### 4.2 前端测试覆盖面不足

**位置**：`AutoTest_Frontend/src/stores/*.test.js`、`AutoTest_Frontend/src/view-models/*.test.js`

**现状**：6 个测试文件，覆盖 store 操作和 view-model helper。无组件挂载测试、无路由测试、无用户交互测试。

**建议**：
- 补充 SettingsView 表单交互测试（保存、重置、刷新）
- 补充 WorkbenchView 生成+执行按钮状态流转测试
- 补充 HistoryView 分页和筛选测试
- 优先级：**P1**

### 4.3 CI 管道缺少覆盖率报告

**位置**：`.github/workflows/ci.yml`

**现状**：CI 只运行测试和构建，不生成覆盖率报告。

**建议**：
- 后端添加 `pytest-cov`（当前使用自定义 runner，需适配）
- 前端引入 `vitest` 后自带 coverage 支持
- 在 CI 中上传覆盖率报告
- 优先级：**P2**

---

## 五、知识库与 RAG 优化点

### 5.1 知识库文档数量不足

**位置**：`AutoTest_Backend/docs/knowledge/`（12 份文档）

**现状**：覆盖了登录、搜索、表单/表格、定位策略、动态页面等基础场景，但缺少以下高频场景：
- 文件上传（`input[type=file]`）
- 下拉选择（select / cascader）
- 多标签页切换
- 鼠标悬停菜单（hover dropdown）
- 拖拽排序
- 表格分页与排序

**建议**：
- 将知识库文档扩充至 ≥18 份
- 每份文档包含：场景描述、Selenium 代码示例、定位策略、常见陷阱
- 优先级：**P1**

### 5.2 RAG 检索质量缺少量化验证

**位置**：`AutoTest_Backend/app/services/rag_service.py`

**现状**：有 3 种检索模式（vector / hybrid / hybrid_rerank），但没有检索质量的量化评估。无法证明 rerank 比纯 vector 更好。

**建议**：
- 编写一组标准 query → expected docs 的评估集
- 对比三种模式的 Precision@K、Recall@K
- 将结果沉淀到实验报告中
- 优先级：**P1**（答辩时可能被追问检索效果）

---

## 六、工程规范优化点

### 6.1 缺少 `.env.example` 的同步机制

**位置**：`AutoTest_Backend/.env.example`

**现状**：`.env.example` 存在但缺少 `FRONTEND_ORIGINS` 等新增的配置项说明。

**建议**：保持 `.env.example` 与 `Settings` 类的字段同步，优先级 **P3**。

### 6.2 `vue-admin-template` 作为 git submodule 更合适

**位置**：`vue-admin-template/` 目录

**现状**：整个 `vue-admin-template` 项目被完整复制到仓库根目录，自带独立的 `.git/` 目录。这增加了仓库体积且不便于更新。

**建议**：
- 改为 git submodule 或将其移到独立仓库
- 在 README 中说明靶场的启动方式
- 优先级：**P3**

### 6.3 无 README 中的快速启动说明

**现状**：根目录没有 `README.md`，无法让新人快速了解项目启动方式。

**建议**：
- 创建根目录 `README.md`，包含项目简介、技术栈、快速启动（后端 + 前端）、测试运行命令
- 优先级：**P1**

---

## 七、优化优先级总览

| 优先级 | 编号 | 优化项 | 所属层 | 预计工作量 |
| --- | --- | --- | --- | --- |
| **P0** | — | 无新 P0（已修复项见 PROJECT_PLAN.md） | — | — |
| **P1** | 2.2 | 后端日志体系 | 后端 | 0.5 天 |
| **P1** | 2.3 | 清理残留的 `run-build.mjs` | 前端 | 0.5 小时 |
| **P1** | 2.5 | 修复异常处理静默 pass | 后端 | 0.5 小时 |
| **P1** | 3.1 | 引入前端测试框架（Vitest） | 前端 | 1 天 |
| **P1** | 3.2 | Settings 页补齐表单标签 | 前端 | 0.5 小时 |
| **P1** | 3.4 | API Client 添加拦截器 | 前端 | 0.5 天 |
| **P1** | 4.1 | 后端 API 集成测试 | 测试 | 1 天 |
| **P1** | 4.2 | 前端组件级测试 | 测试 | 1 天 |
| **P1** | 5.1 | 扩充知识库文档 | RAG | 1-2 天 |
| **P1** | 5.2 | RAG 检索质量量化验证 | RAG | 1 天 |
| **P1** | 6.3 | 根目录 README | 文档 | 0.5 天 |
| **P2** | 2.1 | 数据库连接管理优化 | 后端 | 0.5 天 |
| **P2** | 2.4 | 提取重复工具方法 | 后端 | 0.5 小时 |
| **P2** | 2.6 | 清理 container 冗余写入 | 后端 | 0.5 小时 |
| **P2** | 2.7 | RAG 服务拆分 | 后端 | 1 天 |
| **P2** | 2.8 | 代码安全白名单细化 | 后端 | 0.5 天 |
| **P2** | 3.3 | 前端全局错误边界 | 前端 | 0.5 天 |
| **P2** | 3.6 | 代码编辑器集成 | 前端 | 1 天 |
| **P2** | 3.7 | Metrics 页图表可视化 | 前端 | 1 天 |
| **P2** | 4.3 | CI 覆盖率报告 | CI | 0.5 天 |
| **P3** | 3.5 | i18n 严格响应式 | 前端 | 0.5 天 |
| **P3** | 6.1 | `.env.example` 同步 | 工程 | 0.5 小时 |
| **P3** | 6.2 | `vue-admin-template` 改 submodule | 工程 | 0.5 小时 |

---

## 八、下一步规划

### 阶段 A：工程质量收口（3-4 天）

> 目标：消除已知的工程硬伤，让项目达到"可构建、可测试、可追踪"。

1. **引入后端日志体系**（2.2）：在核心服务中添加结构化日志
2. **清理 `run-build.mjs`**（2.3）：删除残留构建脚本，确认 `npm run build` 正常
3. **修复异常静默 pass**（2.5）：所有 `except: pass` 替换为日志记录
4. **Settings 页补表单标签**（3.2）：为 3 个 input-number 添加 form-item label
5. **API Client 拦截器**（3.4）：添加响应拦截器统一处理错误

### 阶段 B：测试与验证加固（3-4 天）

> 目标：建立可信的自动化验证体系。

1. **引入 Vitest**（3.1）：替换自写测试 runner，获得组件测试能力
2. **后端 API 集成测试**（4.1）：用 TestClient 覆盖核心 API 链路
3. **前端组件测试**（4.2）：Settings / Workbench 的关键交互
4. **RAG 检索质量验证**（5.2）：标准评估集 + 三模式对比

### 阶段 C：知识库与实验数据（3-5 天）

> 目标：扩充 RAG 能力，补齐毕设答辩所需的实验证据。

1. **扩充知识库文档**（5.1）：补 6+ 份场景文档
2. **执行手工实验批次**：完成 F-01 ~ F-05、H-01 ~ H-03 实验并截图
3. **汇总实验指标**：生成首次成功率、自愈率、最终成功率的分组统计
4. **失败案例归因**：分类失败模式，沉淀到文档

### 阶段 D：展示层与文档收口（2-3 天）

> 目标：提升演示观感，完善文档体系。

1. **Metrics 页图表**（3.7）：添加趋势折线图和成功率环形图
2. **代码编辑器**（3.6）：为 Workbench 脚本区集成语法高亮
3. **根目录 README**（6.3）：项目简介 + 快速启动 + 架构概述
4. **架构文档 + API 文档**：补充 `docs/` 下的技术文档

---

## 九、核心结论

1. **后端架构设计扎实**，分层清晰（路由 → 服务 → 仓库 → 数据库），状态机转换有约束，安全校验有白名单。需要优化的是日志、异常处理、连接管理等工程细节。

2. **前端功能完整**，4 个页面覆盖了核心流程。需要补的是测试框架升级、表单可用性、错误处理一致性和可视化图表。

3. **最高优先级不是新功能，而是"可证明性"**：日志体系、测试覆盖、RAG 质量验证、实验数据沉淀。这些决定了答辩和作品集的说服力。

4. **推荐执行路径**：阶段 A（工程收口）→ 阶段 B（测试加固）→ 阶段 C（实验数据）→ 阶段 D（展示收口）。
