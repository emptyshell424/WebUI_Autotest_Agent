# PRD: Agent 智能体核心能力升级

> **版本**: v1.0  
> **日期**: 2026-04-26  
> **状态**: Draft  
> **目标**: 将当前"LLM 辅助脚本生成 + 线性自愈"系统升级为具备规划、感知、推理、记忆、工具调用能力的真正测试智能体。

---

## 1. 现状分析

### 1.1 当前架构能力

| 模块 | 当前实现 | 智能体视角评价 |
|------|----------|---------------|
| **GenerationService** | 单轮 LLM 调用 + RAG 上下文拼接 | 无任务分解，无多步推理 |
| **StrategyService** | 硬编码规则（仅覆盖百度搜索场景） | 不可泛化，新场景必须手写规则 |
| **ExecutionService** | subprocess 执行 + 线性重试 | 无实时 DOM 反馈，无动态调整 |
| **FailureDiagnosticService** | 正则匹配错误关键词 | 无语义理解，误分类率高 |
| **AgentMemoryService** | 自愈成功后写 Markdown 文件 | 只写不读（写后无检索回路） |
| **LLMService** | 单次 chat completion | 无 function calling / tool use |
| **RAGService** | ChromaDB + BM25 hybrid | 仅用于生成阶段，自愈阶段未充分利用 |

### 1.2 核心差距

真正的测试智能体需要具备以下能力环路，当前系统全部缺失或仅部分实现：

```
感知(Perceive) → 规划(Plan) → 执行(Act) → 观察(Observe) → 反思(Reflect) → 记忆(Remember)
     ↑                                                                          │
     └──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 目标定义

### 2.1 核心目标

将系统从 **"Prompt → 生成脚本 → 盲执行 → 线性重试"** 升级为 **"任务理解 → 动态规划 → 工具调用执行 → 实时观察 → 自主修复 → 经验积累"** 的智能体闭环。

### 2.2 成功指标

| 指标 | 当前基线 | 目标值 |
|------|----------|--------|
| 首次生成通过率 | ~40% (估) | ≥70% |
| 自愈成功率 | ~30% (估) | ≥60% |
| 支持场景泛化 | 仅百度搜索有策略 | 任意 Web 场景自适应 |
| 复杂多步任务成功率 | 不支持 | ≥50% |
| 经验复用命中率 | 0 (只写不读) | ≥40% 相似失败命中历史修复 |

---

## 3. 功能模块设计

### 3.1 P0 — Agent Core Loop（智能体核心循环）

**目标**: 引入 ReAct（Reasoning + Acting）范式，让 Agent 具备"思考-行动-观察"循环。

#### 3.1.1 AgentOrchestrator（编排器）

新增顶层编排服务，替代当前 `GenerationService` + `ExecutionService` 的线性拼接。

```
用户 Prompt
    │
    ▼
┌─ AgentOrchestrator ──────────────────────────────────────┐
│                                                           │
│  1. TaskAnalyzer: 理解意图，分解为子任务                      │
│  2. Planner: 生成执行计划（可包含多个 step）                  │
│  3. ReAct Loop:                                           │
│     ┌─ Thought: LLM 推理当前状态 + 下一步行动               │
│     │  Action: 选择并调用 Tool                             │
│     │  Observation: 获取工具返回结果                        │
│     └─ 循环直到任务完成或达到 max_steps                     │
│  4. Reflector: 执行结束后反思成功/失败原因                   │
│  5. MemoryWriter: 沉淀经验到长期记忆                       │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

#### 3.1.2 Tool Registry（工具注册表）

将 Agent 可调用的能力抽象为标准化 Tool，通过 LLM function calling 动态选择：

| Tool 名称 | 描述 | 对应当前能力 |
|-----------|------|-------------|
| `generate_selenium_script` | 根据自然语言生成 Selenium 脚本 | GenerationService |
| `execute_script` | 执行 Python Selenium 脚本并返回结果 | ExecutionService._execute_script |
| `analyze_page_dom` | 获取当前页面 DOM 快照（简化） | 新增 |
| `search_knowledge` | 在知识库中检索相关文档 | RAGService.search |
| `search_memory` | 检索历史修复经验 | AgentMemoryService（增强） |
| `diagnose_failure` | 对执行失败进行语义诊断 | FailureDiagnosticService（增强） |
| `repair_script` | 基于诊断结果修复脚本 | LLMService.repair_script |
| `validate_code` | 安全校验生成代码 | validate_generated_code |
| `take_screenshot` | 截取当前浏览器页面截图 | 新增 |

### 3.2 P0 — Task Understanding & Planning（任务理解与规划）

#### 3.2.1 TaskAnalyzer

替代当前 `StrategyService` 中的硬编码规则匹配：

```python
# 当前方式（硬编码）
if "搜索" in prompt and "百度" in prompt:
    site_profile = "baidu_search"

# 升级为 LLM 驱动的意图分析
class TaskAnalyzer:
    def analyze(self, prompt: str) -> TaskAnalysis:
        """
        输出:
        - intent: 用户意图（login / search / navigate / form_fill / verify ...）
        - target_site: 目标站点特征
        - steps: 预期操作步骤列表
        - preconditions: 前置条件
        - success_criteria: 成功判定标准
        - complexity: simple / multi_step / complex_flow
        """
```

**关键设计**: 使用 LLM structured output (JSON mode) 提取结构化任务分析，而非正则匹配。

#### 3.2.2 Planner

对复杂任务生成可执行的分步计划：

```
输入: "打开 vue-admin-template，用 admin/111111 登录，进入用户管理页面，搜索用户 test"

输出 Plan:
  Step 1: navigate_to("http://localhost:9528")
  Step 2: login(username="admin", password="111111")
  Step 3: wait_for_dashboard()
  Step 4: navigate_to_menu("用户管理")
  Step 5: search_user("test")
  Step 6: verify_search_results()
```

### 3.3 P0 — Intelligent Self-Heal（智能自愈升级）

#### 3.3.1 LLM-Driven Failure Diagnosis

将 `FailureDiagnosticService` 从正则匹配升级为 LLM 语义分析：

```python
class IntelligentDiagnosticService:
    def diagnose(self, *, error, logs, code, dom_snapshot=None) -> FailureDiagnosis:
        """
        1. 将 error + logs + code + 可选 DOM 快照送入 LLM
        2. LLM 输出结构化诊断:
           - failure_type (语义级别，不再依赖正则)
           - root_cause_analysis (深度分析，非模板句)
           - repair_strategy (具体修复策略，非通用 hint)
           - confidence (诊断置信度)
        3. 低置信度时触发 DOM 探查获取更多上下文
        """
```

#### 3.3.2 Adaptive Repair Strategy

替代当前的线性重试循环，引入自适应修复策略选择：

```
失败 → 诊断 → 查询历史记忆 → 选择修复策略
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              选择器修复      等待策略调整      交互路径降级
              (定位问题)      (时序问题)        (流程问题)
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
                              执行修复脚本
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
                  成功         失败(换策略)     失败(升级)
                                    │               │
                                    ▼               ▼
                             尝试下一策略     请求人工介入
```

### 3.4 P1 — Agent Memory System（智能体记忆系统）

#### 3.4.1 短期记忆（Working Memory）

当前执行会话内的上下文窗口管理：

```python
class WorkingMemory:
    """单次任务执行过程中的上下文"""
    task_analysis: TaskAnalysis           # 任务理解结果
    execution_plan: list[PlanStep]        # 执行计划
    action_history: list[ActionRecord]    # 已执行动作及结果
    dom_observations: list[DOMSnapshot]   # 页面观察记录
    current_code: str                     # 当前脚本版本
    accumulated_errors: list[str]         # 累计错误信息
```

#### 3.4.2 长期记忆（Long-term Memory）

将当前只写不读的 `AgentMemoryService` 升级为可检索的经验库：

```
写入时机:
  - 自愈成功 → 写入 "修复经验卡片"（当前已有）
  - 首次成功 → 写入 "成功模式卡片"（新增）
  - 多次失败 → 写入 "已知陷阱卡片"（新增）

读取时机（当前完全缺失，需新增）:
  - 生成阶段 → 检索相似场景的成功模式
  - 自愈阶段 → 检索相似失败的修复经验
  - 规划阶段 → 检索相似任务的执行计划模板
```

**实现方式**: 复用现有 ChromaDB + RAG 基础设施，新增 `memory` collection，将记忆卡片向量化存储，在各阶段注入检索结果。

#### 3.4.3 站点画像（Site Profile）

替代硬编码的 `SITE_PROFILE_BAIDU_SEARCH`，建立动态站点模型：

```python
class SiteProfile:
    """通过历史执行数据自动构建的站点知识"""
    site_url: str
    known_selectors: dict[str, str]      # 已验证的稳定选择器
    page_load_patterns: dict             # 各页面加载特征
    common_failure_patterns: list        # 该站点常见失败模式
    successful_strategies: list          # 历史成功策略
    avg_load_time: float                 # 平均加载时间
    last_updated: datetime
```

### 3.5 P1 — DOM Perception（页面感知能力）

#### 3.5.1 Lightweight DOM Observer

在脚本执行失败时，启动浏览器获取页面实时状态：

```python
class DOMObserver:
    """轻量级页面感知"""
    
    def capture_page_state(self, url: str) -> PageState:
        """
        返回:
        - title: 页面标题
        - url: 当前 URL
        - visible_text: 可见文本摘要（前 2000 字符）
        - interactive_elements: 可交互元素列表
          [{"tag": "input", "id": "kw", "name": "wd", "placeholder": "..."}, ...]
        - forms: 表单结构
        - error_indicators: 页面错误提示
        """
    
    def get_element_context(self, url: str, selector: str) -> ElementContext:
        """获取特定元素的周围上下文"""
```

**关键约束**: 不是全量 DOM dump，而是提取 LLM 可理解的结构化摘要，控制 token 消耗。

### 3.6 P2 — Multi-Model Strategy（多模型策略）

#### 3.6.1 模型路由

根据任务复杂度和阶段选择不同模型，平衡成本与质量：

| 阶段 | 推荐模型 | 理由 |
|------|----------|------|
| 任务分析 / 规划 | deepseek-chat (当前) | 结构化输出，低成本 |
| 代码生成 | deepseek-coder / 更强模型 | 代码质量要求高 |
| 失败诊断 | deepseek-chat | 推理型任务 |
| 经验检索排序 | embedding model | 向量相似度 |

```python
class ModelRouter:
    def select_model(self, task_type: str, complexity: str) -> ModelConfig:
        """根据任务类型和复杂度选择最合适的模型"""
```

### 3.7 P2 — Streaming & Observability（流式输出与可观测性）

#### 3.7.1 Agent 思考过程可视化

前端实时展示 Agent 的推理链路：

```
[Thinking] 分析用户意图: 这是一个百度搜索任务...
[Planning] 生成执行计划: 3 个步骤...
[Action]   调用工具: generate_selenium_script
[Observe]  脚本生成完成, 48 行代码
[Action]   调用工具: execute_script
[Observe]  执行失败: TimeoutException at line 23
[Thinking] 诊断失败原因: 搜索框选择器变更...
[Memory]   找到 1 条相似修复经验
[Action]   调用工具: repair_script
[Observe]  修复脚本执行成功
[Reflect]  记录修复经验到长期记忆
```

**实现**: WebSocket / SSE 推送 Agent 每一步的状态变化。

---

## 4. 技术架构

### 4.1 新增模块

```
app/
├── services/
│   ├── agent_orchestrator.py      # [新增] 智能体编排器（核心）
│   ├── task_analyzer.py           # [新增] LLM 驱动的任务分析
│   ├── planner.py                 # [新增] 任务规划器
│   ├── tool_registry.py           # [新增] 工具注册表
│   ├── working_memory.py          # [新增] 工作记忆
│   ├── dom_observer.py            # [新增] 页面感知
│   ├── model_router.py            # [新增] 模型路由
│   ├── agent_memory_service.py    # [重构] 增加读取检索能力
│   ├── failure_diagnostic_service.py  # [重构] LLM 驱动诊断
│   ├── strategy_service.py        # [重构] 泛化策略，去硬编码
│   ├── execution_service.py       # [重构] 接入编排器
│   ├── generation_service.py      # [重构] 接入编排器
│   ├── llm_service.py             # [增强] 支持 function calling
│   └── rag_service.py             # [增强] 支持 memory collection
├── tools/                         # [新增] Agent 可调用工具实现
│   ├── __init__.py
│   ├── base.py                    # Tool 基类定义
│   ├── generate_tool.py
│   ├── execute_tool.py
│   ├── dom_tool.py
│   ├── knowledge_tool.py
│   ├── memory_tool.py
│   ├── diagnose_tool.py
│   └── screenshot_tool.py
└── api/
    └── routes/
        └── agent.py               # [新增] Agent 专用 API 端点
```

### 4.2 数据模型扩展

```sql
-- 新增: 任务分析记录
CREATE TABLE task_analysis (
    id TEXT PRIMARY KEY,
    execution_id TEXT REFERENCES execution_record(id),
    prompt TEXT NOT NULL,
    intent TEXT,                    -- login / search / navigate / ...
    complexity TEXT,                -- simple / multi_step / complex_flow
    plan_json TEXT,                 -- 结构化执行计划
    analysis_model TEXT,            -- 使用的分析模型
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 新增: Agent 动作日志
CREATE TABLE agent_action_log (
    id TEXT PRIMARY KEY,
    execution_id TEXT REFERENCES execution_record(id),
    step_number INTEGER NOT NULL,
    thought TEXT,                   -- LLM 推理内容
    action_type TEXT,               -- tool_call / observe / reflect
    tool_name TEXT,                 -- 调用的工具名
    tool_input TEXT,                -- 工具输入参数 (JSON)
    tool_output TEXT,               -- 工具输出结果 (JSON)
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 新增: 站点画像
CREATE TABLE site_profile (
    id TEXT PRIMARY KEY,
    site_url TEXT NOT NULL UNIQUE,
    known_selectors TEXT,           -- JSON
    failure_patterns TEXT,          -- JSON
    successful_strategies TEXT,     -- JSON
    execution_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 扩展现有表
ALTER TABLE execution_record ADD COLUMN agent_mode TEXT DEFAULT 'legacy';
ALTER TABLE execution_record ADD COLUMN total_agent_steps INTEGER DEFAULT 0;
ALTER TABLE execution_record ADD COLUMN total_llm_calls INTEGER DEFAULT 0;
ALTER TABLE execution_record ADD COLUMN total_tokens_used INTEGER DEFAULT 0;
```

### 4.3 API 扩展

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/agent/run` | 启动 Agent 模式执行（替代 generate + execute 两步） |
| GET | `/api/v1/agent/run/{id}/stream` | SSE 流式获取 Agent 执行过程 |
| GET | `/api/v1/agent/run/{id}/trace` | 获取完整 Agent 推理链路 |
| GET | `/api/v1/agent/memory/search` | 搜索 Agent 长期记忆 |
| GET | `/api/v1/agent/profiles` | 获取所有站点画像 |
| POST | `/api/v1/agent/analyze` | 仅执行任务分析（不生成脚本） |

---

## 5. 执行计划

### Phase 0: 基础稳定（前置条件）

> **时间**: 1 周  
> **依据**: `DEVELOPMENT_STATUS_NEXT_STEPS.md` 的结论 — 在加功能前先证明系统可信。

| # | 任务 | 产出 |
|---|------|------|
| 0.1 | 跑通全量后端测试，清理失败清单 | 测试全绿或已知原因列表 |
| 0.2 | 端到端主流程验证（前端→生成→执行→自愈→结果） | 主流程可演示 |
| 0.3 | 修复 execution_service / self_heal 关键缺陷 | 执行链可靠 |

### Phase 1: Agent 内核 — ReAct 循环 + 工具化

> **时间**: 2-3 周  
> **核心交付**: 系统从"线性管道"变为"循环智能体"

| # | 任务 | 详细描述 | 可用 AI 加速 |
|---|------|----------|-------------|
| 1.1 | **LLMService 增强 — 支持 function calling** | 在 `_complete` 中增加 `tools` 参数支持；封装 tool schema 生成 | AI 生成 tool schema JSON |
| 1.2 | **Tool 基础框架** | 创建 `app/tools/base.py`，定义 `BaseTool` 抽象类 + `ToolRegistry` | AI 生成框架代码 |
| 1.3 | **现有能力工具化** | 将 `generate_selenium_script`、`execute_script`、`search_knowledge`、`validate_code` 封装为 Tool | AI 将现有 service 方法包装为 Tool |
| 1.4 | **AgentOrchestrator 核心循环** | 实现 ReAct loop：Thought → Action → Observation → 循环 | AI 生成编排循环骨架 |
| 1.5 | **WorkingMemory** | 实现单次执行的上下文管理，控制 token 窗口 | AI 生成数据结构 |
| 1.6 | **Agent API 端点** | `POST /agent/run` + SSE `/agent/run/{id}/stream` | AI 生成 FastAPI route |
| 1.7 | **集成测试** | 验证 Agent 模式可完成简单任务（打开页面、搜索） | AI 生成测试用例 |

### Phase 2: 智能诊断 + 记忆增强

> **时间**: 2 周  
> **核心交付**: 自愈从"盲修"变为"基于诊断和经验的精准修复"

| # | 任务 | 详细描述 | 可用 AI 加速 |
|---|------|----------|-------------|
| 2.1 | **LLM 驱动的 TaskAnalyzer** | 替代 StrategyService 硬编码规则，使用 LLM structured output 提取意图 | AI 设计 prompt + output schema |
| 2.2 | **IntelligentDiagnosticService** | 将失败诊断从正则升级为 LLM 语义分析 | AI 设计诊断 prompt |
| 2.3 | **AgentMemoryService 读取增强** | 在 ChromaDB 中建 `agent_memory` collection，支持相似经验检索 | AI 设计 embedding + 检索逻辑 |
| 2.4 | **记忆注入到自愈流程** | 自愈前检索相似失败的历史修复经验，注入 repair prompt | AI 设计记忆注入 prompt 模板 |
| 2.5 | **成功模式 + 已知陷阱记忆** | 首次成功/多次失败也写入记忆 | AI 生成 memory card 模板 |
| 2.6 | **自适应修复策略选择** | 基于诊断结果 + 历史记忆动态选择修复策略 | AI 设计策略选择 prompt |
| 2.7 | **回归测试** | 确保新诊断不低于旧正则匹配的准确率 | AI 生成对比测试 |

### Phase 3: 页面感知 + 站点画像

> **时间**: 2 周  
> **核心交付**: Agent 获得"看到页面"的能力

| # | 任务 | 详细描述 | 可用 AI 加速 |
|---|------|----------|-------------|
| 3.1 | **DOMObserver 实现** | Selenium 驱动的轻量 DOM 快照提取 | AI 生成 DOM 解析逻辑 |
| 3.2 | **DOM 摘要压缩** | 将完整 DOM 压缩为 LLM 可理解的结构化摘要（控制 token） | AI 设计压缩算法 |
| 3.3 | **DOM Tool 集成** | 将 DOM 观察作为 Tool 接入 Agent 循环 | AI 生成 tool wrapper |
| 3.4 | **Screenshot Tool** | 执行失败时截图，支持视觉分析（如使用多模态模型） | AI 生成截图逻辑 |
| 3.5 | **SiteProfile 动态构建** | 基于历史执行数据自动构建站点画像 | AI 生成聚合分析逻辑 |
| 3.6 | **站点画像注入生成** | 生成脚本时注入目标站点的已知选择器和失败模式 | AI 设计注入 prompt |

### Phase 4: 多步任务 + 模型优化

> **时间**: 2 周  
> **核心交付**: Agent 可处理复杂多步测试场景

| # | 任务 | 详细描述 | 可用 AI 加速 |
|---|------|----------|-------------|
| 4.1 | **Planner 实现** | 复杂任务自动分解为子步骤执行计划 | AI 设计 planning prompt |
| 4.2 | **多步脚本组合执行** | 按 Plan 逐步生成并执行脚本，前一步结果注入下一步 | AI 生成组合执行逻辑 |
| 4.3 | **ModelRouter 实现** | 根据任务阶段和复杂度路由到不同模型 | AI 生成路由规则 |
| 4.4 | **Token 消耗优化** | 实现上下文窗口滑动、摘要压缩、选择性注入 | AI 设计压缩策略 |
| 4.5 | **前端 Agent Trace 可视化** | 展示 Agent 完整推理链路 | AI 生成 Vue 组件 |
| 4.6 | **端到端验收** | 复杂场景测试（登录→导航→搜索→验证） | AI 生成验收用例 |

---

## 6. AI 辅助开发策略

以下是每个开发步骤中可以直接利用 AI（如 Cascade / Copilot）加速的具体方式：

### 6.1 代码生成类

| 任务 | AI 指令模板 |
|------|------------|
| Tool 基类 + Registry | "创建 `app/tools/base.py`，包含 `BaseTool` 抽象类（name, description, parameters_schema, execute 方法）和 `ToolRegistry` 管理类" |
| 现有 Service 工具化 | "将 `GenerationService.generate` 包装为符合 `BaseTool` 接口的 `GenerateScriptTool`，参数为 prompt + retrieval_mode" |
| AgentOrchestrator | "创建 `agent_orchestrator.py`，实现 ReAct 循环：接收 prompt → 调用 LLM with tools → 解析 tool_call → 执行 tool → 收集 observation → 循环" |
| 数据库迁移 | "为 SQLite 新增 task_analysis, agent_action_log, site_profile 三张表的建表 SQL，集成到 `database.py` 的 initialize_database" |

### 6.2 Prompt 工程类

| 任务 | AI 指令模板 |
|------|------------|
| TaskAnalyzer prompt | "设计一个 system prompt，让 LLM 分析用户的自然语言测试需求，输出 JSON 格式的 intent / complexity / steps / success_criteria" |
| 智能诊断 prompt | "设计一个 prompt，输入 error + logs + code，输出结构化的 failure_type / root_cause / repair_strategy / confidence" |
| 记忆检索排序 | "设计 prompt 让 LLM 对检索到的 3 条历史修复经验按相关度排序，选出最适合当前失败的经验" |

### 6.3 测试生成类

| 任务 | AI 指令模板 |
|------|------------|
| Tool 单元测试 | "为 `GenerateScriptTool` 生成 unittest，mock LLM 调用，验证 Tool 接口正确性" |
| Agent 循环测试 | "为 `AgentOrchestrator` 生成集成测试，mock 所有 tool，验证 ReAct 循环在 3 步内完成简单任务" |
| 记忆读写测试 | "测试 AgentMemoryService 的写入和检索，验证相似失败可以命中历史修复经验" |

---

## 7. 风险与约束

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM 调用成本增加 | 多步循环 = 多次 LLM 调用，token 成本上升 | ModelRouter 分流 + 上下文压缩 + max_steps 硬限 |
| Agent 循环不收敛 | 可能陷入无限推理循环 | 设置 max_agent_steps（默认 10），超限强制终止 |
| Function calling 兼容性 | DeepSeek 的 function calling 能力可能弱于 GPT-4 | 准备 fallback 到 prompt-based tool selection |
| 记忆污染 | 错误的修复经验被记忆，导致后续误导 | 记忆写入需通过置信度阈值 + 支持人工标记/删除 |
| 前置稳定性不足 | Phase 0 未完成就开始 Agent 开发 | 严格按 Phase 顺序执行，Phase 0 是硬性前置 |

---

## 8. 兼容性策略

- **渐进式升级**: 保留现有 `/generate` + `/executions` API 不变（`legacy` 模式），新增 `/agent/run`（`agent` 模式）
- **Feature Flag**: 通过 `system_setting` 中的 `agent_mode_enabled` 控制是否启用 Agent 模式
- **向后兼容**: 前端可同时使用旧模式和新模式，通过 UI 开关切换
- **数据兼容**: 新表独立，不修改现有表结构，仅通过 ALTER TABLE 追加可选列

---

## 9. 里程碑总览

```
Week 1        Week 2-3       Week 4-5       Week 6-7       Week 8-9
  │              │              │              │              │
  ▼              ▼              ▼              ▼              ▼
Phase 0       Phase 1        Phase 2        Phase 3        Phase 4
基础稳定     Agent 内核     智能诊断+记忆   页面感知+画像   多步任务+优化
  │              │              │              │              │
  ▼              ▼              ▼              ▼              ▼
测试全绿     ReAct 循环     LLM 诊断       DOM 观察       复杂场景
主流程通     工具化完成     记忆读写闭环    站点画像       端到端验收
```

---

## 10. 立即可执行的第一步

在正式开始 Phase 1 之前，建议先完成一个最小 PoC 验证 Agent 循环的可行性:

1. **在 `llm_service.py` 中测试 DeepSeek 的 function calling 能力** — 确认当前使用的模型是否支持 `tools` 参数
2. **如果不支持**: 设计 prompt-based tool selection 的 fallback 方案（在 prompt 中描述可用工具，让 LLM 输出 JSON 格式的工具调用）
3. **最小循环验证**: 用 2 个 tool（generate + execute）跑通一个"生成 → 执行 → 成功/失败"的单次 ReAct 循环

这个 PoC 的结果将决定 Phase 1 的具体技术路线。
