# WebUI AutoTest Agent — 执行计划

> 基于 `OPTIMIZATION_AUDIT.md` 审计结果整理
> 创建时间：2026-04-23
> 总预估工期：12-16 个工作日（4 个阶段）

---

## 执行原则

1. **按阶段推进，严格串行**。阶段内任务可并行，但阶段间存在依赖。
2. **每个任务有明确的验收标准**。不满足验收标准不进入下一个任务。
3. **P1 必须完成，P2 争取完成，P3 视时间裁剪**。
4. **优先稳定性和可证明性，其次是展示层打磨**。

---

## 阶段 A：工程质量收口

> 预计工期：3-4 天
> 目标：消除工程硬伤，让项目达到"可构建、可测试、可追踪"的最低标准。
> 前置条件：无

### A-1 引入后端日志体系

| 字段 | 内容 |
| --- | --- |
| **审计编号** | 2.2 |
| **优先级** | P1 |
| **预计工时** | 4 小时 |
| **负责模块** | `AutoTest_Backend/app/core/`、`AutoTest_Backend/app/services/` |

**执行步骤**：

1. 新建 `AutoTest_Backend/app/core/logger.py`
   - 使用 `logging.getLogger("autotest")` 创建项目级 logger
   - 配置 `StreamHandler`，格式含时间戳、级别、模块名
   - 暴露 `get_logger(name)` 工厂函数

2. 在以下服务文件顶部添加 `logger = get_logger(__name__)`：
   - `execution_service.py`
   - `generation_service.py`
   - `llm_service.py`
   - `rag_service.py`
   - `strategy_service.py`

3. 关键日志埋点：
   - `LLMService._complete()`：记录请求模型、token 数量、响应耗时
   - `ExecutionService.create_execution()`：记录 test_case_id、执行开始
   - `ExecutionService._execute_script()`：记录脚本路径、执行结果（成功/失败/超时）
   - `ExecutionService._try_self_heal()`：记录每轮修复的触发原因和结果
   - `RAGService.search()`：记录 query、检索模式、返回文档数量

**验收标准**：

- [ ] 后端启动后，控制台可见结构化日志输出
- [ ] 执行一次完整的生成→执行流程，能从日志中追踪每个环节
- [ ] 所有 `except Exception: pass` 已替换为 `logger.exception()`
- [ ] 后端测试 30/30 仍然全部通过

---

### A-2 清理残留构建脚本

| 字段 | 内容 |
| --- | --- |
| **审计编号** | 2.3 |
| **优先级** | P1 |
| **预计工时** | 30 分钟 |
| **负责模块** | `AutoTest_Frontend/scripts/` |

**执行步骤**：

1. 删除 `AutoTest_Frontend/scripts/run-build.mjs`
2. 确认 `package.json` 的 `build` 脚本为 `vite build`（当前已是）
3. 确认 `vite.config.js` 包含完整的 `manualChunks` 配置（当前已有）
4. 执行 `npm run build`，验证构建成功

**验收标准**：

- [ ] `run-build.mjs` 已从仓库中删除
- [ ] `npm run build` 成功产出 `dist/` 目录
- [ ] `npm run dev` 和 `npm test` 不受影响

---

### A-3 修复异常处理静默 pass

| 字段 | 内容 |
| --- | --- |
| **审计编号** | 2.5 |
| **优先级** | P1 |
| **预计工时** | 30 分钟 |
| **负责模块** | `AutoTest_Backend/app/services/execution_service.py`、`AutoTest_Backend/app/services/rag_service.py` |

**执行步骤**：

1. `execution_service.py` 第 217-218 行：
   ```python
   # 修改前
   except Exception:
       pass
   # 修改后
   except Exception:
       logger.exception("Failed to mark execution %s as failed", execution_id)
   ```

2. `rag_service.py` `_reset_collection()` 方法：
   ```python
   # 修改前
   except Exception:
       pass
   # 修改后
   except Exception:
       logger.warning("Failed to delete collection %s, continuing rebuild", self.collection_name)
   ```

3. 全局搜索 `except Exception: pass`，逐一替换

**验收标准**：

- [ ] 仓库中不存在 `except Exception: pass`（或 `except Exception:\n\s+pass`）
- [ ] 后端测试 30/30 通过

---

### A-4 Settings 页补齐表单标签

| 字段 | 内容 |
| --- | --- |
| **审计编号** | 3.2 |
| **优先级** | P1 |
| **预计工时** | 30 分钟 |
| **负责模块** | `AutoTest_Frontend/src/views/SettingsView.vue`、`AutoTest_Frontend/src/i18n/index.js` |

**执行步骤**：

1. 在 `i18n/index.js` 的 `en.settings` 和 `zh-CN.settings` 中新增：
   - `executionTimeoutLabel` / `执行超时（秒）`
   - `maxSelfHealLabel` / `最大自愈次数`
   - `maxConcurrentLabel` / `最大并发执行数`

2. 在 `SettingsView.vue` 中用 `<el-form>` + `<el-form-item :label="t('settings.xxxLabel')">` 包裹三个 `<el-input-number>`

3. 在 `main.js` 中确认 `ElForm` 和 `ElFormItem` 已注册（如未注册则补上）

**验收标准**：

- [ ] Settings 页每个数字输入框前有清晰的中英文标签
- [ ] 中英文切换后标签正确更新
- [ ] `npm test` 通过

---

### A-5 API Client 添加响应拦截器

| 字段 | 内容 |
| --- | --- |
| **审计编号** | 3.4 |
| **优先级** | P1 |
| **预计工时** | 4 小时 |
| **负责模块** | `AutoTest_Frontend/src/api/client.js` |

**执行步骤**：

1. 在 `apiClient` 创建后设置初始 `baseURL`：
   ```javascript
   const apiClient = axios.create({
     baseURL: getStoredApiBaseUrl(),
     timeout: 60000,
   })
   ```

2. 添加响应拦截器：
   ```javascript
   apiClient.interceptors.response.use(
     (response) => response,
     (error) => {
       // 统一提取错误信息
       // 网络错误 / 超时 / 5xx 可在此统一处理
       return Promise.reject(error)
     }
   )
   ```

3. 确认现有 store 中的 `extractApiError()` 调用不受影响

**验收标准**：

- [ ] 应用启动时 `apiClient` 已有 `baseURL`，无需等 `bootstrap()`
- [ ] 后端未启动时，前端 API 调用显示友好错误提示而非白屏
- [ ] `npm test` 通过

---

## 阶段 B：测试与验证加固

> 预计工期：3-4 天
> 目标：建立可信的自动化验证体系。
> 前置条件：阶段 A 全部完成

### B-1 引入 Vitest 前端测试框架

| 字段 | 内容 |
| --- | --- |
| **审计编号** | 3.1 |
| **优先级** | P1 |
| **预计工时** | 1 天 |
| **负责模块** | `AutoTest_Frontend/` |

**执行步骤**：

1. 安装依赖：
   ```bash
   npm install -D vitest @vue/test-utils happy-dom
   ```

2. 在 `vite.config.js` 中添加 test 配置：
   ```javascript
   test: {
     environment: 'happy-dom',
     include: ['src/**/*.test.js'],
   }
   ```

3. 将 `package.json` 的 `test` 脚本改为 `vitest run`

4. 迁移现有 6 个 `.test.js` 文件：
   - 将 `node:assert/strict` 替换为 `vitest` 的 `expect` / `describe` / `it`
   - 移除 `run-tests.mjs` 中的全局 `window` 模拟（happy-dom 自带）

5. 验证全部现有测试通过

**验收标准**：

- [ ] `npm test` 使用 vitest 运行
- [ ] 现有 6 个测试文件全部迁移并通过
- [ ] `run-tests.mjs` 不再被 `package.json` 引用
- [ ] CI 中 `npm test` 仍然正常

---

### B-2 后端 API 集成测试

| 字段 | 内容 |
| --- | --- |
| **审计编号** | 4.1 |
| **优先级** | P1 |
| **预计工时** | 1 天 |
| **负责模块** | `AutoTest_Backend/tests/` |

**执行步骤**：

1. 新建 `AutoTest_Backend/tests/test_api_integration.py`

2. 使用 FastAPI `TestClient` + 临时 SQLite 数据库 + mock LLM

3. 编写以下集成测试用例：
   - `test_health_returns_status`：`GET /api/v1/health` 返回完整健康信息
   - `test_generate_creates_test_case`：`POST /api/v1/generate` 返回生成结果
   - `test_create_execution`：`POST /api/v1/executions` 创建执行任务
   - `test_get_execution_detail`：`GET /api/v1/executions/{id}` 返回执行详情
   - `test_list_executions_with_pagination`：`GET /api/v1/executions` 支持分页
   - `test_cancel_execution`：`DELETE /api/v1/executions/{id}` 取消执行
   - `test_get_stats`：`GET /api/v1/executions/stats` 返回统计数据
   - `test_settings_get_and_update`：`GET/PUT /api/v1/settings` 读写配置

4. 将新测试文件集成到 `run_backend_tests.py`

**验收标准**：

- [ ] 新增 ≥8 个集成测试用例
- [ ] `python AutoTest_Backend/run_backend_tests.py` 全量通过（30 + 新增）
- [ ] 测试使用临时目录，不影响开发数据库

---

### B-3 前端组件级测试

| 字段 | 内容 |
| --- | --- |
| **审计编号** | 4.2 |
| **优先级** | P1 |
| **预计工时** | 1 天 |
| **负责模块** | `AutoTest_Frontend/src/views/` |

**执行步骤**：

1. 新建 `AutoTest_Frontend/src/views/SettingsView.test.js`：
   - 组件能正常挂载
   - 表单字段渲染正确数量的 input-number
   - 保存按钮点击触发 store action
   - 错误提示正确显示

2. 新建 `AutoTest_Frontend/src/views/WorkbenchView.test.js`：
   - 组件能正常挂载
   - 生成按钮在 prompt 为空时禁用
   - 运行按钮在无 case 时禁用
   - 生成成功后编辑区有内容

3. 新建 `AutoTest_Frontend/src/views/HistoryView.test.js`：
   - 组件能正常挂载
   - 筛选器切换触发 store 重新获取
   - 分页组件渲染正确

**验收标准**：

- [ ] 新增 ≥3 个组件测试文件
- [ ] 每个文件 ≥3 个测试用例
- [ ] `npm test` 全部通过

---

### B-4 RAG 检索质量量化验证

| 字段 | 内容 |
| --- | --- |
| **审计编号** | 5.2 |
| **优先级** | P1 |
| **预计工时** | 1 天 |
| **负责模块** | `AutoTest_Backend/` |

**执行步骤**：

1. 新建 `AutoTest_Backend/tests/test_rag_retrieval_quality.py`

2. 定义标准评估集（≥10 组 query → expected document 映射）：
   ```python
   EVAL_SET = [
       {"query": "打开百度搜索关键词", "expected_docs": ["search_flows.md"]},
       {"query": "登录后台管理系统", "expected_docs": ["login_flows.md"]},
       {"query": "操作 Element UI 表单", "expected_docs": ["element_ui_form_table_patterns.md"]},
       # ...
   ]
   ```

3. 对每组 query 分别用 `vector` / `hybrid` / `hybrid_rerank` 检索

4. 计算每种模式的命中率（top-3 中是否包含 expected_docs）

5. 将结果输出为 Markdown 表格，沉淀到 `AutoTest_Backend/docs/EXPERIMENT_RESULTS.md`

**验收标准**：

- [ ] 评估集 ≥10 组
- [ ] 三种检索模式的命中率对比表已生成
- [ ] `hybrid_rerank` 命中率 ≥ `vector`（否则需分析原因）

---

## 阶段 C：知识库与实验数据

> 预计工期：3-5 天
> 目标：扩充 RAG 能力，补齐答辩所需的实验证据。
> 前置条件：阶段 B 全部完成

### C-1 扩充知识库文档

| 字段 | 内容 |
| --- | --- |
| **审计编号** | 5.1 |
| **优先级** | P1 |
| **预计工时** | 1-2 天 |
| **负责模块** | `AutoTest_Backend/docs/knowledge/` |

**执行步骤**：

1. 编写以下 6 份新文档（每份含场景描述 + Selenium 代码示例 + 定位策略 + 常见陷阱）：

   | 文件名 | 覆盖场景 |
   | --- | --- |
   | `file_upload_patterns.md` | 文件上传（`input[type=file]`、拖拽上传） |
   | `select_dropdown_patterns.md` | 下拉选择（原生 select、Element Plus select、cascader） |
   | `tab_switch_patterns.md` | 多标签页切换（el-tabs、自定义 tab） |
   | `hover_menu_patterns.md` | 鼠标悬停菜单、tooltip、dropdown menu |
   | `drag_sort_patterns.md` | 拖拽排序（sortable list、drag-and-drop） |
   | `table_pagination_patterns.md` | 表格分页、排序、筛选 |

2. 每份文档遵循现有文档格式：以 `Keywords:` 开头

3. 执行知识库重建：`POST /api/v1/knowledge/rebuild`

4. 用 B-4 的评估脚本验证新文档被正确检索

**验收标准**：

- [ ] 知识库文档 ≥18 份
- [ ] 每份新文档有 ≥1 个完整的 Selenium 代码示例
- [ ] 知识库重建成功，新文档可被检索命中

---

### C-2 执行首批手工实验

| 字段 | 内容 |
| --- | --- |
| **关联文档** | `EXPERIMENT_SCENARIOS.md`、`EXPERIMENT_RESULTS.md` |
| **优先级** | P1 |
| **预计工时** | 2-3 天 |
| **负责模块** | 全系统端到端 |

**执行步骤**：

1. 启动本地靶场（`vue-admin-template`）+ 后端 + 前端

2. 逐个执行 F-01 ~ F-05（首次生成场景）：

   | 步骤 | 记录内容 |
   | --- | --- |
   | 输入 prompt | 原文截图 |
   | 生成脚本 | 脚本摘要 + 完整代码 |
   | 首次执行 | 成功/失败 + 错误信息 |
   | 自愈触发 | 是/否 + 修复摘要 |
   | 最终结果 | 状态 + 截图 |
   | 历史/指标 | 记录更新截图 |

3. 逐个执行 H-01 ~ H-03（自愈场景）：
   - 构造可控的首次失败（错误选择器 / 过短等待）
   - 记录修复前后代码对比
   - 截图：首次失败 vs 自愈成功

4. 更新 `EXPERIMENT_RESULTS.md`，将状态从 Pending → Verified

**验收标准**：

- [ ] ≥5 个首次生成场景有 Verified 结果
- [ ] ≥2 个自愈场景有修复前后对比证据
- [ ] 每个场景有 ≥2 张截图（输入 + 结果）

---

### C-3 汇总实验指标

| 字段 | 内容 |
| --- | --- |
| **优先级** | P1 |
| **预计工时** | 0.5 天 |
| **负责模块** | `docs/` |

**执行步骤**：

1. 从已完成的实验中提取：
   - 首次成功率 = 首次通过数 / 总执行数
   - 自愈触发率 = 触发自愈数 / 总失败数
   - 自愈成功率 = 修复成功数 / 触发自愈数
   - 最终成功率 = (首次通过 + 修复成功) / 总执行数

2. 按场景类型分组统计（首次生成组 / 自愈组）

3. 输出 Markdown 汇总表

4. 对失败案例归因分类（选择器失效 / 等待不足 / 逻辑错误 / 其他）

**验收标准**：

- [ ] 指标汇总表已写入 `EXPERIMENT_RESULTS.md`
- [ ] 失败案例有分类和归因分析
- [ ] 指标数据与 Metrics 页展示一致

---

## 阶段 D：展示层与文档收口

> 预计工期：2-3 天
> 目标：提升演示观感，完善文档体系。
> 前置条件：阶段 C 全部完成

### D-1 Metrics 页图表可视化

| 字段 | 内容 |
| --- | --- |
| **审计编号** | 3.7 |
| **优先级** | P2 |
| **预计工时** | 1 天 |
| **负责模块** | `AutoTest_Frontend/src/views/MetricsView.vue` |

**执行步骤**：

1. 安装 `echarts` + `vue-echarts`（或直接用 echarts）
2. 在 MetricsView 中添加两个图表：
   - **趋势折线图**：横轴日期，纵轴首次成功 / 修复成功 / 失败数量
   - **成功率环形图**：首次成功率 / 自愈成功率 / 最终成功率
3. 在 `main.js` 中注册图表组件

**验收标准**：

- [ ] Metrics 页展示 ≥2 个图表
- [ ] 图表数据与后端 `/stats` 返回一致
- [ ] 中英文标签正确

---

### D-2 代码编辑器集成

| 字段 | 内容 |
| --- | --- |
| **审计编号** | 3.6 |
| **优先级** | P2 |
| **预计工时** | 1 天 |
| **负责模块** | `AutoTest_Frontend/src/views/WorkbenchView.vue` |

**执行步骤**：

1. 安装 `codemirror` + `@codemirror/lang-python` + `@codemirror/theme-one-dark`（或等价轻量方案）
2. 封装一个 `<CodeEditor>` 组件，支持 `v-model`、Python 语法高亮、行号
3. 替换 WorkbenchView 中的 `<el-input type="textarea">`
4. 保持只读模式与可编辑模式的切换

**验收标准**：

- [ ] 生成脚本区显示 Python 语法高亮
- [ ] 有行号显示
- [ ] 用户仍可编辑代码后执行

---

### D-3 根目录 README

| 字段 | 内容 |
| --- | --- |
| **审计编号** | 6.3 |
| **优先级** | P1 |
| **预计工时** | 0.5 天 |
| **负责模块** | 仓库根目录 |

**执行步骤**：

1. 创建 `README.md`，包含以下章节：
   - 项目简介（一句话定义 + 核心能力）
   - 技术栈表格
   - 系统架构图（文本版）
   - 快速启动（后端 + 前端，含前置条件）
   - 测试运行命令（后端 + 前端）
   - 目录结构说明
   - 文档索引（指向 `docs/` 下各文档）
   - 已知限制

**验收标准**：

- [ ] README 包含完整的快速启动步骤
- [ ] 新人按 README 可以从零启动项目
- [ ] 文档索引覆盖 `docs/` 下所有文档

---

### D-4 补充技术文档

| 字段 | 内容 |
| --- | --- |
| **优先级** | P1 |
| **预计工时** | 0.5 天 |
| **负责模块** | `docs/` |

**执行步骤**：

1. 更新 `docs/PROJECT_TECHNICAL_DOCUMENTATION.md`：
   - 补充 API 接口的请求/响应示例
   - 补充实体关系图（test_case → execution_record → self_heal_attempt）
   - 补充状态机流转图
   - 补充部署注意事项

2. 确保 `docs/` 下所有文档的更新时间与内容一致

**验收标准**：

- [ ] API 文档有 ≥4 个端点的请求/响应示例
- [ ] 数据实体关系有可视化说明
- [ ] 状态流转有完整描述

---

## 可选任务（时间充足时执行）

以下任务为 P2/P3，不纳入主线阶段约束：

| 编号 | 任务 | 审计编号 | 预计工时 | 建议时机 |
| --- | --- | --- | --- | --- |
| O-1 | 数据库连接管理优化 | 2.1 | 0.5 天 | 阶段 A 后 |
| O-2 | 提取重复工具方法 | 2.4 | 0.5 小时 | 阶段 A 后 |
| O-3 | 清理 container 冗余写入 | 2.6 | 0.5 小时 | 阶段 A 后 |
| O-4 | RAG 服务文件拆分 | 2.7 | 1 天 | 阶段 B 后 |
| O-5 | 安全白名单细化 | 2.8 | 0.5 天 | 阶段 B 后 |
| O-6 | 前端全局错误边界 | 3.3 | 0.5 天 | 阶段 A 后 |
| O-7 | CI 覆盖率报告 | 4.3 | 0.5 天 | 阶段 B 后 |
| O-8 | i18n 严格响应式 | 3.5 | 0.5 天 | 阶段 D 后 |
| O-9 | `.env.example` 同步 | 6.1 | 0.5 小时 | 阶段 A 后 |
| O-10 | `vue-admin-template` 改 submodule | 6.2 | 0.5 小时 | 阶段 D 后 |

---

## 时间线概览

```
Week 1
├── Day 1-2: 阶段 A（工程质量收口）
│   ├── A-1 后端日志体系
│   ├── A-2 清理残留构建脚本
│   ├── A-3 修复异常处理静默 pass
│   ├── A-4 Settings 页补表单标签
│   └── A-5 API Client 拦截器
│
├── Day 3-4: 阶段 A 收尾 + 阶段 B 启动
│   ├── A 阶段验收确认
│   └── B-1 引入 Vitest
│
├── Day 5-7: 阶段 B（测试与验证加固）
│   ├── B-2 后端 API 集成测试
│   ├── B-3 前端组件级测试
│   └── B-4 RAG 检索质量验证

Week 2
├── Day 8-10: 阶段 C（知识库与实验数据）
│   ├── C-1 扩充知识库文档
│   └── C-2 执行首批手工实验（启动）
│
├── Day 11-12: 阶段 C 继续
│   ├── C-2 手工实验（完成）
│   └── C-3 汇总实验指标
│
├── Day 13-14: 阶段 D（展示层与文档收口）
│   ├── D-1 Metrics 页图表
│   ├── D-2 代码编辑器
│   ├── D-3 根目录 README
│   └── D-4 技术文档补充

Day 15-16: 缓冲 + 可选任务
│   ├── 处理阶段中遗留的问题
│   └── 执行 O-1 ~ O-10 中的高收益项
```

---

## 阶段验收检查清单

### 阶段 A 完成标准

- [ ] 后端有结构化日志输出
- [ ] 无 `except Exception: pass`
- [ ] `run-build.mjs` 已删除
- [ ] Settings 页表单标签齐全
- [ ] API Client 有 baseURL 和响应拦截器
- [ ] `npm run build` 成功
- [ ] 后端测试 30/30 通过
- [ ] 前端测试全部通过

### 阶段 B 完成标准

- [ ] 前端使用 Vitest 运行测试
- [ ] 后端新增 ≥8 个 API 集成测试
- [ ] 前端新增 ≥3 个组件测试文件
- [ ] RAG 三模式检索质量对比表已生成
- [ ] CI pipeline 仍然全绿

### 阶段 C 完成标准

- [ ] 知识库文档 ≥18 份
- [ ] ≥5 个首次生成场景有 Verified 结果和截图
- [ ] ≥2 个自愈场景有修复前后对比
- [ ] 实验指标汇总表已生成
- [ ] 失败案例有归因分析

### 阶段 D 完成标准

- [ ] Metrics 页有 ≥2 个可视化图表
- [ ] Workbench 脚本区有语法高亮
- [ ] 根目录 README 可指导新人启动项目
- [ ] 技术文档有 API 示例和实体关系说明

### 项目最终验收标准

- [ ] 端到端主流程（生成 → 执行 → 自愈 → 历史 → 指标）可完整演示
- [ ] 后端测试 ≥38 个用例全部通过
- [ ] 前端测试 ≥15 个用例全部通过
- [ ] 至少 5 个实验场景有完整证据
- [ ] 项目文档体系完整，可支撑答辩
