# WebUI AutoTest Agent 下一阶段需求与一周迭代计划

> 更新日期：2026-04-24  
> 文档用途：毕业设计冲刺阶段的需求文档、迭代计划、答辩叙事依据  
> 时间假设：答辩大约在 2026 年 5 月上旬到 5 月中旬，实际日期未确定  
> 核心判断：下一阶段不是继续堆页面，而是把“RAG + 自愈 Agent”做成可演示、可解释、可写论文的闭环。

## 1. 背景与问题判断

当前项目已经不是从零开始的原型。代码中已经具备以下基础能力：

- FastAPI 后端、Vue 前端、`vue-admin-template` 被测系统。
- 基于知识库文档的 RAG 检索，支持 `vector`、`hybrid`、`hybrid_rerank` 三种检索模式。
- 自然语言生成 Selenium 测试脚本。
- 执行脚本、记录日志、记录执行状态。
- 失败后调用 LLM 修复脚本，并可根据 `MAX_SELF_HEAL_ATTEMPTS` 配置进行多轮修复。
- 修复尝试记录，包括失败原因、修复摘要、修复前后代码、策略变化、日志等。
- 指标统计，包括首次成功率、自愈触发率、自愈成功率、最终成功率。
- 后端自动化测试当前可通过，最近验证结果为 `62/62`。

但当前项目仍然不足以支撑高质量答辩，主要问题是：

1. “Agent 智能体”的定义不够明确。  
   现在更像“失败后调用 LLM 修脚本的循环”，还没有被清晰表达为“观察、诊断、决策、修复、验证、记忆”的智能体闭环。

2. RAG 的论文叙事不够强。  
   代码里有检索、查询扩展、混合排序、重排序，但需要讲清楚为什么这样做、输入输出是什么、对生成质量有什么帮助。

3. 缺少长期记忆能力。  
   用户目标选择的是 D：Agent 能维护长期记忆，把失败案例沉淀进知识库。当前知识库主要是静态文档，成功修复经验还没有形成稳定的知识沉淀闭环。

4. 缺少可答辩证据。  
   目前自动化测试能证明后端局部逻辑，但还缺少登录、表格查询、自愈成功三个演示场景的正式实验记录、截图和对比数据。

5. 部分文档和知识库内容存在编码污染。  
   例如部分中文内容显示为乱码。这会直接影响 RAG 叙事和答辩观感，必须作为 P0 问题处理。

## 2. 下一阶段总目标

在一周内，将项目收敛为一个可毕业答辩、可系统演示、可写进简历的版本：

> 基于 RAG + LLM Agent 的 Web UI 自动化测试平台。用户输入自然语言测试需求，系统检索领域知识，生成 Selenium 测试脚本，执行脚本并观察失败信息；当脚本无法达到预期时，Agent 基于失败日志、原始代码、RAG 上下文和历史修复经验进行多轮自愈，并将成功修复案例沉淀为可复用知识。

这个目标必须同时满足三个场景：

- 毕业答辩：能讲清楚项目是做什么的、RAG 怎么实现、Agent 在哪里、创新点是什么、工作量在哪里。
- 系统演示：能现场跑通核心闭环，不依赖外部不稳定网站。
- 简历表达：能体现后端工程、AI 应用、RAG、Agent、自愈测试、实验评估。

## 3. 范围定义

### 3.1 本阶段必须做

本阶段聚焦以下能力：

1. 明确定义并实现 Agent 闭环：
   - Plan：根据用户需求和 RAG 上下文生成测试计划或策略。
   - Generate：生成 Selenium 测试脚本。
   - Act：执行脚本。
   - Observe：收集 stdout、stderr、异常、状态、截图或页面证据。
   - Diagnose：识别失败类型。
   - Repair：生成修复脚本。
   - Verify：重新执行修复脚本。
   - Memorize：把成功修复经验沉淀为可复用知识。

2. 修复 RAG 中文知识库和别名乱码问题。

3. 实现或补强长期记忆能力：
   - 成功自愈后生成结构化“修复经验卡片”。
   - 经验卡片进入知识库或待审核知识库。
   - 后续生成和修复时能够检索到这些经验。

4. 固化三个答辩演示场景：
   - 登录测试。
   - 表格页面测试。
   - 故意失败后自愈成功。

5. 形成实验数据：
   - 不使用 RAG vs 使用 RAG。
   - 首次执行 vs 自愈后执行。
   - 无记忆 vs 有修复记忆。

6. 输出答辩可用材料：
   - 架构图。
   - RAG 流程说明。
   - Agent 闭环流程说明。
   - 实验结果表。
   - 工作量说明。

### 3.2 本阶段明确不做

以下内容不作为一周内的主要目标：

- 不追求工业级通用 Web 自动化测试平台。
- 不做复杂权限、多用户、团队协作。
- 不做大规模外部网站测试。
- 不把 UI 重设计作为重点。
- 不优先引入 LangChain 或 LangGraph。当前代码已有执行编排基础，P0 目标是把本项目已有闭环补完整、讲清楚，而不是为引入框架而引入框架。
- 不追求覆盖所有 Selenium 异常类型，只覆盖答辩演示和论文实验需要的典型失败。

## 4. 用户与使用场景

### 4.1 目标用户

本阶段的主要用户不是企业真实测试团队，而是：

- 毕业答辩评审老师。
- 项目开发者本人。
- 简历筛选时看到项目介绍的面试官。

因此系统优先满足“可解释、可演示、可证明”，而不是只追求功能数量。

### 4.2 核心使用场景

#### 场景 1：登录测试生成与执行

用户输入自然语言：

```text
打开本地 vue-admin-template 登录页，输入用户名 admin 和密码 111111，点击 Login，验证进入 Dashboard。
```

系统行为：

1. RAG 检索登录流程、Element UI 输入框、显式等待、断言规则。
2. LLM 生成 Selenium 脚本。
3. 执行脚本。
4. 验证页面跳转或 Dashboard 文本。
5. 成功后记录执行结果。

验收标准：

- 生成脚本包含明确的登录输入、点击和成功断言。
- 执行结果为 `completed`。
- History 中可查看执行记录。
- Metrics 中指标更新。

#### 场景 2：表格页面测试

用户输入自然语言：

```text
登录 vue-admin-template 后打开 Example/Table 页面，等待表格加载完成，验证表格中存在 Title、Author、Pageviews、Status 列。
```

系统行为：

1. RAG 检索表格页面、异步加载、Element UI Table、稳定断言规则。
2. LLM 生成 Selenium 脚本。
3. 执行脚本。
4. 等待 loading 消失或表格出现。
5. 验证表头和至少一行数据。

验收标准：

- 生成脚本不只打开页面，还要等待表格加载。
- 断言包含表头或行数据。
- 执行结果为 `completed`。

#### 场景 3：故意失败后的自愈成功

用户输入自然语言：

```text
登录 vue-admin-template 后打开 Example/Table 页面，等待表格加载完成并验证表头。
```

人为制造失败：

- 将生成脚本中的某个稳定选择器改错，例如把 `table` 相关定位改成不存在的选择器。
- 或把等待时间改得过短，制造 `TimeoutException`。

系统行为：

1. 初次执行失败。
2. Agent 收集错误日志和失败代码。
3. Agent 诊断失败类型，例如选择器失效或等待不足。
4. Agent 调用 RAG 和修复提示生成修复脚本。
5. 重新执行修复脚本。
6. 修复成功后记录自愈尝试。
7. 把成功修复案例沉淀为长期记忆。

验收标准：

- 初次执行状态为 `failed` 或触发自愈。
- 至少产生 1 条 `self_heal_attempt`。
- 最终状态为 `healed_completed`。
- 修复记录中能看到失败原因、修复摘要、原代码、修复代码。
- 生成一条可检索的修复经验卡片。

## 5. Agent 能力定义

### 5.1 本项目中的 Agent 不是聊天机器人

答辩时不要把 Agent 讲成“用了大模型所以就是智能体”。这说法站不住。

本项目中的 Agent 应定义为：

> 一个围绕 Web UI 测试任务运行的闭环控制器。它能够基于自然语言目标生成动作，执行动作，观察环境反馈，分析失败原因，选择修复策略，多轮验证结果，并把成功经验沉淀为后续可检索知识。

### 5.2 Agent 闭环状态机

建议将 Agent 逻辑表达为以下状态机：

```text
User Goal
  -> Retrieve Knowledge
  -> Generate Script
  -> Execute Script
  -> Observe Result
  -> Success?
       -> Yes: Save Result
       -> No: Diagnose Failure
              -> Select Repair Strategy
              -> Repair Script
              -> Re-execute
              -> Success?
                   -> Yes: Save Result + Write Memory
                   -> No: Retry until limit or mark healed_failed
```

### 5.3 最低可交付 Agent 能力

一周内最低必须做到：

- 能多轮修复，次数由 `MAX_SELF_HEAL_ATTEMPTS` 控制。
- 能识别至少 3 类失败：
  - 选择器失效。
  - 等待超时。
  - 断言失败。
- 能为不同失败类型生成不同修复提示。
- 能记录每次修复的输入、输出、策略和结果。
- 能将成功修复案例转化为长期记忆。
- 后续生成或修复时能够检索到长期记忆。

### 5.4 不建议的一周内做法

不建议立即引入 LangGraph 作为 P0。原因：

- 当前项目已有生成、执行、自愈、记录和指标链路。
- LangGraph 会增加论文解释成本和调试成本。
- 老师更关心你是否讲清楚系统原理，而不是用了哪个框架。

可以在论文展望中写：

> 后续可使用 LangGraph 等框架将当前有限状态机式 Agent 升级为更标准的图式工作流编排。

## 6. RAG 能力定义

### 6.1 当前 RAG 流程

当前项目的 RAG 可以解释为：

1. 将知识库 Markdown 文档切分为 chunk。
2. 使用 ChromaDB 建立向量索引；当 ChromaDB 不可用时，回退到本地 BM25 风格检索。
3. 对用户输入进行查询扩展，例如登录、表格、搜索、等待、断言等关键词。
4. 支持三种检索模式：
   - `vector`：向量检索。
   - `hybrid`：向量分数 + BM25 分数 + 来源提示分数。
   - `hybrid_rerank`：先召回候选，再按关键词命中、来源提示和文档质量重排序。
5. 将检索到的上下文拼入 LLM prompt。
6. LLM 基于用户需求、知识上下文和策略上下文生成脚本。

### 6.2 RAG 在论文中的作用

RAG 的作用不是“让系统看起来高级”，而是解决三个具体问题：

- 降低 LLM 幻觉：让模型参考本项目真实页面、Element UI 组件、Selenium 写法。
- 提高生成稳定性：补充显式等待、稳定断言、安全导入等规则。
- 支持经验复用：把成功修复案例沉淀后，后续相似失败可被检索出来。

### 6.3 下一步 RAG 必修项

P0：

- 修复知识库和 `rag_service.py` 中的中文乱码。
- 补充 `vue-admin-template` 登录、表格、路由、Element UI Table 的知识文档。
- 为三个答辩场景分别验证 RAG 召回内容是否正确。

P1：

- 增加“修复经验记忆”知识来源。
- 在实验中比较：
  - 无 RAG。
  - 静态 RAG。
  - 静态 RAG + 修复记忆。

## 7. 长期记忆需求

### 7.1 为什么需要长期记忆

你选择的 Agent 目标是 D：能维护长期记忆，把失败案例沉淀进知识库。

如果没有长期记忆，系统只能说“会调用大模型修复”。这不够像 Agent，也不足以作为论文亮点。

长期记忆要证明：

- Agent 不是每次从零开始。
- 成功修复经验可以复用。
- RAG 不只用于生成前的静态知识，也能吸收运行后的经验。

### 7.2 记忆内容格式

建议每条记忆采用结构化 Markdown：

```markdown
## Memory: selector_timeout_table_header

Target app: vue-admin-template
Scenario: table page header verification
Failure type: wait_timeout
Failure signal: TimeoutException while waiting for table header
Root cause: table data loads asynchronously and the script checked header too early
Repair action: wait until `.el-table` is visible and loading mask disappears before asserting headers
Stable selectors:
- `.el-table`
- `.el-table__header`
- text: Title
- text: Author
Validation rule: assert table headers contain Title, Author, Pageviews, Status
```

### 7.3 记忆落地方案

一周内建议采用简单方案：

- 新增目录：`AutoTest_Backend/docs/knowledge/agent_memory/`
- 每次成功自愈后生成一份 Markdown 记忆卡片。
- 记忆卡片由后端生成，文件名包含日期、场景和失败类型。
- RAG 重建索引时将这些记忆卡片纳入检索。

可选增强：

- 增加 `MemoryService`，负责生成、保存、读取记忆。
- 增加 API：`POST /api/v1/knowledge/memories/rebuild` 或复用现有知识库重建接口。
- 前端在执行详情中展示“已沉淀为知识”的状态。

风险：

- 自动写入知识库可能污染 RAG。  
  缓解：只在 `healed_completed` 且修复代码通过安全校验时写入；记忆内容必须结构化，不能直接保存整段失败代码作为主要检索内容。

## 8. 功能需求

### FR-1：Agent 编排服务

需求：

- 新增或明确一个 Agent 编排层，用于表达完整闭环。
- 即使内部复用现有 `GenerationService`、`ExecutionService`、`StrategyService`，也要有清晰的 Agent 入口和日志。

建议实现：

- 新增 `AgentService` 或 `SelfHealAgentService`。
- 负责组织：
  - RAG 检索。
  - 生成。
  - 执行。
  - 失败诊断。
  - 修复。
  - 记忆写入。

验收：

- 代码中能明确指出 Agent 入口。
- 答辩时能展示 Agent 流程图并对应到代码模块。

### FR-2：失败类型诊断

需求：

- Agent 需要根据错误日志和脚本内容识别失败类型。

最低支持：

- `selector_not_found`
- `wait_timeout`
- `assertion_failed`
- `safety_blocked`
- `unknown_failure`

输入：

- stderr。
- stdout。
- 原始脚本。
- 用户 prompt。
- RAG context。

输出：

- failure_type。
- failure_signal。
- suspected_root_cause。
- repair_hint。

验收：

- 至少 3 类失败有单元测试。
- 执行详情中能看到失败类型或修复摘要。

### FR-3：策略化修复

需求：

- 不同失败类型使用不同修复提示，而不是一段通用 prompt。

示例：

- 选择器失效：要求优先使用文本、name、placeholder、表头文本等稳定定位。
- 等待超时：要求改用显式等待，等待 loading 消失或目标元素可见。
- 断言失败：要求修复断言目标，不能绕过断言直接打印成功。

验收：

- 自愈记录中能看到策略化修复摘要。
- 故意失败场景能够修复成功。

### FR-4：长期记忆沉淀

需求：

- 成功自愈后，生成修复经验卡片。
- 经验卡片可被 RAG 检索。

验收：

- `healed_completed` 后产生一条 memory 文档。
- 重建知识库后，类似场景 prompt 能召回该 memory。
- 实验结果中能展示“记忆写入前后”的对比。

### FR-5：RAG 中文和场景知识修复

需求：

- 修复乱码中文别名。
- 补充 `vue-admin-template` 的登录和表格测试知识。

验收：

- 中文 prompt 能召回正确知识文档。
- `登录` prompt 命中登录文档。
- `表格` prompt 命中表格或 Element UI Table 文档。
- 后端 RAG 测试覆盖真实中文词，不再只覆盖英文或乱码词。

### FR-6：答辩演示场景固化

需求：

- 固化 3 个场景的 prompt、预期结果、截图清单、实验记录。

验收：

- `AutoTest_Backend/docs/EXPERIMENT_RESULTS.md` 中至少有 3 条 Verified：
  - 登录测试。
  - 表格页面测试。
  - 自愈成功测试。
- 每条记录包含：
  - prompt。
  - 生成脚本摘要。
  - 首次执行结果。
  - 自愈结果。
  - 执行记录 id。
  - 截图路径。

## 9. 非功能需求

### 9.1 可解释性

系统必须能解释：

- 本次用了哪些知识文档。
- 为什么选择某种修复策略。
- 失败原因是什么。
- 修复前后有什么变化。
- 是否写入长期记忆。

### 9.2 可复现性

答辩演示必须依赖本地 `vue-admin-template`，避免外部网站变化导致演示失败。

最低运行链路：

```text
Backend: http://127.0.0.1:8000
Frontend: http://127.0.0.1:5173
Target SUT: http://127.0.0.1:9528
```

### 9.3 安全性

生成和修复脚本必须继续保留安全校验：

- 禁止危险 import。
- 禁止文件系统、系统命令、网络低层调用等无关能力。
- 修复脚本也必须通过安全校验。

### 9.4 可靠性

核心后端测试必须保持通过：

```powershell
python .\AutoTest_Backend\run_backend_tests.py
```

当前基线：`62/62 OK`。

前端测试当前在本地 sandbox 下运行被环境阻断，需要后续在正常终端或 CI 中复验，不能直接归因于业务代码失败。

## 10. 一周迭代计划

### Day 1：代码和文档基线收敛

目标：

- 修复 RAG 和知识库中文乱码。
- 明确 Agent 目标和模块边界。
- 建立演示场景清单。

任务：

- 修复 `rag_service.py` 中中文别名乱码。
- 检查 `AutoTest_Backend/docs/knowledge/*.md` 中文内容，重写污染严重的文档。
- 补充 `vue-admin-template` 登录和表格测试知识。
- 为三个演示场景写标准 prompt。
- 跑后端测试，确保基线不退化。

交付：

- 中文 RAG 检索正常。
- 登录、表格 prompt 能召回正确知识。
- 后端测试通过。

### Day 2：Agent 诊断与策略化修复

目标：

- 让自愈不是单纯重试，而是有失败诊断和策略选择。

任务：

- 新增失败诊断模型或函数。
- 支持选择器失效、等待超时、断言失败三类诊断。
- 将诊断结果加入修复 prompt。
- 将诊断结果写入自愈记录或修复摘要。
- 补充单元测试。

交付：

- 3 类失败可被识别。
- 修复提示随失败类型变化。
- 测试通过。

### Day 3：长期记忆能力

目标：

- 实现成功自愈经验沉淀。

任务：

- 新增 `agent_memory` 知识目录。
- 新增 memory 生成逻辑。
- 在 `healed_completed` 后生成结构化 memory。
- 确保 RAG 重建时纳入 memory。
- 增加测试：成功自愈后产生 memory，重建后可检索。

交付：

- 自愈成功后产生记忆卡片。
- 记忆能被 RAG 检索。

### Day 4：三条演示链路打通

目标：

- 固化登录、表格、自愈三个演示场景。

任务：

- 启动后端、前端、`vue-admin-template`。
- 跑登录生成与执行。
- 跑表格生成与执行。
- 人工制造失败并跑自愈。
- 记录执行 id、截图路径、生成脚本摘要。

交付：

- 至少 3 个 Verified 场景。
- 至少 1 个 `healed_completed` 场景。

### Day 5：实验对比

目标：

- 形成论文可用对比。

任务：

- 对比无 RAG、静态 RAG、静态 RAG + Agent memory。
- 每个场景至少跑 3 次，记录首次成功率和最终成功率。
- 汇总：
  - 首次成功率。
  - 自愈触发率。
  - 自愈成功率。
  - 最终成功率。

交付：

- 实验结果表。
- 可用于论文和 PPT 的指标。

### Day 6：答辩叙事和项目文档

目标：

- 把技术讲法固定下来。

任务：

- 更新架构文档。
- 写 RAG 原理说明。
- 写 Agent 原理说明。
- 写系统使用说明。
- 写工作量说明。
- 整理文档目录。

交付：

- 答辩讲稿素材。
- 论文技术章节素材。
- 简历项目描述。

### Day 7：演示彩排与兜底方案

目标：

- 保证答辩当天可演示。

任务：

- 完整跑一遍演示流程。
- 准备截图版兜底证据。
- 准备老师提问回答。
- 准备失败时的解释：外部 API、浏览器驱动、端口占用、模型波动。

交付：

- 演示 checklist。
- PPT 素材。
- 常见问题回答。

## 11. 验收标准

一周后项目至少要满足：

- [ ] 后端测试通过。
- [ ] 中文 RAG 检索无明显乱码污染。
- [ ] 登录测试场景可生成并执行成功。
- [ ] 表格页面测试场景可生成并执行成功。
- [ ] 故意失败场景可触发自愈并最终成功。
- [ ] 自愈过程有失败诊断和策略化修复摘要。
- [ ] 成功自愈后能生成长期记忆。
- [ ] 长期记忆可被 RAG 重新检索。
- [ ] 实验结果中至少有 3 条 Verified 场景。
- [ ] 有对比实验表，能说明 RAG 和 Agent 的效果。
- [ ] 有架构图、RAG 流程图、Agent 闭环图。
- [ ] 能用 3 分钟讲清楚项目做什么，用 5 分钟讲清楚技术实现。

## 12. 论文写作方向

论文题目可以考虑：

```text
基于 RAG 与 LLM Agent 的 Web UI 自动化测试脚本生成与自愈系统设计与实现
```

### 12.1 研究问题

论文可以围绕以下问题展开：

1. 如何将自然语言测试需求转化为可执行 Web UI 自动化测试脚本？
2. 如何通过 RAG 引入领域知识，提高测试脚本生成的稳定性？
3. 如何设计 LLM Agent，使其在脚本执行失败后自动诊断、修复并验证？
4. 如何将成功修复经验沉淀为长期记忆，提高后续相似任务表现？

### 12.2 创新点

不要夸大创新。建议这样表述：

- 将 RAG 引入 Web UI 测试脚本生成，使 LLM 能结合页面模式、Selenium 规则和项目知识生成脚本。
- 设计面向测试执行的自愈 Agent 闭环，实现“生成、执行、观察、诊断、修复、验证、记忆”流程。
- 将修复成功案例结构化沉淀为知识库记忆，使系统具备经验复用能力。
- 构建基于本地 `vue-admin-template` 的可复现实验场景，对比 RAG 和 Agent 自愈带来的效果。

### 12.3 对比实验设计

建议实验组：

| 组别 | RAG | Agent 自愈 | Agent 记忆 | 目的 |
| --- | --- | --- | --- | --- |
| Baseline | 否 | 否 | 否 | 验证纯 LLM 生成能力 |
| RAG | 是 | 否 | 否 | 验证知识检索对首次生成的帮助 |
| RAG + Self-Heal | 是 | 是 | 否 | 验证失败后自愈能力 |
| RAG + Self-Heal + Memory | 是 | 是 | 是 | 验证长期记忆复用能力 |

建议指标：

- 首次生成成功率。
- 自愈触发率。
- 自愈成功率。
- 最终成功率。
- 平均修复轮次。
- 失败类型分布。

## 13. 答辩问答准备

### Q1：你的项目是用来干什么的？

回答要点：

本项目用于降低 Web UI 自动化测试脚本编写和维护成本。用户只需要输入自然语言测试需求，系统会结合知识库生成 Selenium 脚本，执行脚本并记录结果。当脚本因为选择器变化、等待不足、断言错误等原因失败时，自愈 Agent 会分析失败日志，修复脚本并重新执行，成功修复后还会把经验沉淀到知识库。

### Q2：RAG 在项目中是怎么实现的？

回答要点：

项目把 Selenium 编写规范、Element UI 组件模式、登录流程、表格页面、常见失败等知识整理为 Markdown 文档。后端将文档切分成 chunk，使用 ChromaDB 做向量检索，并结合 BM25 和来源权重做混合检索与重排序。用户输入 prompt 后，系统先检索相关知识，再把知识上下文、策略上下文和用户需求一起发送给 LLM，从而提高脚本生成质量。

### Q3：Agent 在哪里？

回答要点：

Agent 不是单次 LLM 调用，而是一个闭环控制流程。它包括目标理解、知识检索、脚本生成、执行、观察失败、诊断原因、选择修复策略、生成修复脚本、重新执行和经验沉淀。项目中的自愈链路和长期记忆共同构成 Agent。

### Q4：你做了什么工作？

回答要点：

可以按模块回答：

- 搭建 FastAPI 后端和 Vue 前端。
- 设计测试脚本生成、执行和记录接口。
- 构建 RAG 知识库和混合检索逻辑。
- 设计 LLM prompt 和安全校验规则。
- 实现脚本执行、自愈修复、多轮重试和状态记录。
- 实现执行历史、指标统计和前端工作台。
- 设计实验场景并收集对比数据。

### Q5：和普通自动化测试有什么区别？

回答要点：

普通自动化测试需要人工写脚本，页面变化后也要人工维护。本项目尝试让系统根据自然语言生成脚本，并在失败后自动分析和修复。它不是替代所有人工测试，而是降低脚本编写和维护成本。

## 14. 简历描述建议

项目名称：

```text
基于 RAG + LLM Agent 的 Web UI 自动化测试脚本生成与自愈平台
```

简历描述：

```text
设计并实现基于 FastAPI、Vue、Selenium、ChromaDB 和 OpenAI-compatible LLM 的 Web UI 自动化测试平台，支持自然语言生成测试脚本、RAG 知识增强、多轮自愈修复、执行历史追踪和指标统计。构建面向测试失败的 Agent 闭环，实现失败日志观察、错误类型诊断、策略化脚本修复、重新执行验证和成功案例记忆沉淀，提升测试脚本生成与维护效率。
```

技术点：

- FastAPI / Vue / Selenium
- RAG / ChromaDB / Hybrid Retrieval
- LLM Prompt Engineering
- Self-Healing Agent
- SQLite / Execution Metrics
- Web UI Automation Testing

## 15. 文档整理策略

当前仓库已有大量文档，但存在三个问题：

- 部分文档内容重复。
- 部分文档已经过期。
- 部分中文内容编码污染。

不建议立刻直接删除，因为其中可能包含历史决策和任务记录。建议按以下方式整理：

### 15.1 保留为主文档

- `README.md`
- `docs/NEXT_ITERATION_REQUIREMENTS.md`
- `docs/ARCHITECTURE.md`
- `AutoTest_Backend/docs/EXPERIMENT_SCENARIOS.md`
- `AutoTest_Backend/docs/EXPERIMENT_RESULTS.md`

### 15.2 后续重写或修复

- `docs/PROJECT_TECHNICAL_DOCUMENTATION.md`
- `docs/PROJECT_SUMMARY.md`
- `docs/PROJECT_PLAN.md`
- `docs/DEVELOPMENT_STATUS_NEXT_STEPS.md`
- `AutoTest_Backend/docs/knowledge/*.md`

### 15.3 建议归档而不是删除

可以新建：

```text
docs/archive/
```

把过期计划、旧审计、旧任务规格移动进去。这样答辩前主文档目录更清晰，同时不丢历史记录。

候选归档：

- `docs/OPTIMIZATION_AUDIT.md`
- `docs/PROJECT_ISSUES_AUDIT.md`
- `docs/TASK_SPEC_TEMPLATE.md`
- `docs/TASK_SPEC_EXPERIMENT_RESULTS.md`
- `docs/UNFINISHED_TASKS.md`
- `docs/EXECUTION_PLAN.md`
- `docs/AI_EXECUTION_INSTRUCTIONS.md`

是否归档要在修复乱码和确认内容价值后执行。

## 16. 当前最重要的下一步

不要先做 PPT，也不要先继续扩页面。

下一步应该按这个顺序执行：

1. 修复 RAG 中文知识和乱码。
2. 实现 Agent 长期记忆。
3. 增加失败诊断和策略化修复。
4. 固化三个演示场景。
5. 收集实验数据。
6. 再整理论文和 PPT。

如果代码功能没有完成，文档写得再好也撑不住答辩；但如果代码已有功能讲不清楚，同样会被认为工作量不足。因此本阶段必须代码和叙事同步推进。
