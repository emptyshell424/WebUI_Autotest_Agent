# 项目问题排查记录

## 排查范围

- 仓库根目录说明文档、前后端关键入口、构建脚本、部分测试文件与核心服务代码
- 实际执行了前端构建校验
- 实际尝试了后端测试，并对数据库初始化做了最小化隔离验证

## 排查结论

当前项目不是“整体不可用”，但存在几类很明确的问题：

1. 前端构建链路存在确定性故障，当前 `npm run build` 失败。
2. 前端组件注册与页面实际用法不一致，设置页存在运行时风险。
3. 后端“运行时设置”接口存在能力表达不一致，接口返回字段与可修改字段不匹配。
4. RAG 相关中文词表/测试样例存在明显编码污染，已经影响可维护性，并大概率影响中文检索质量。
5. 测试链路稳定性不足，当前仓库很难作为“可一键验证”的工程样板。

---

## 已验证问题

### 1. 前端生产构建当前失败

**结论**

`AutoTest_Frontend` 当前无法通过生产构建，这不是潜在风险，是已复现问题。

**复现方式**

在 `AutoTest_Frontend` 目录执行：

```powershell
npm run build
```

**实际现象**

Vite 构建失败，报错位置落在：

- `AutoTest_Frontend/node_modules/vue-router/dist/vue-router.js`

报错核心内容是：

- `{}.NODE_ENV !== "production"` 触发了解析错误

**根因判断**

问题不在业务页面，而在自定义构建脚本 [run-build.mjs](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Frontend/scripts/run-build.mjs:45)。

该脚本会复制一份本地 Vite，并强行替换内部 `replaceDefine` 实现，使用字符串替换方式处理 `define`：

- [run-build.mjs](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Frontend/scripts/run-build.mjs:45)
- [run-build.mjs](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Frontend/scripts/run-build.mjs:47)
- [run-build.mjs](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Frontend/scripts/run-build.mjs:49)

这种实现会把类似 `process.env.NODE_ENV` 的表达式替成 `{}.NODE_ENV`，最终生成非法 JS。这个方案本身就非常脆弱。

**影响**

- 项目无法产出生产包
- 答辩/演示时很难证明“可部署”
- 构建问题来自工具链 hack，后续升级 Vite 时极易再次出问题

**建议优先级**

P0，应该优先修复。

---

### 2. 设置页使用了未注册的 Element Plus 组件

**结论**

前端当前采用“手动注册组件”的方式，但页面实际使用的组件集合与注册列表不一致。

**证据**

设置页使用了 `el-input-number`：

- [SettingsView.vue](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Frontend/src/views/SettingsView.vue:43)
- [SettingsView.vue](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Frontend/src/views/SettingsView.vue:44)
- [SettingsView.vue](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Frontend/src/views/SettingsView.vue:45)

但入口文件的手动注册列表里没有 `ElInputNumber`，也没有对应样式引入：

- [main.js](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Frontend/src/main.js:3)
- [main.js](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Frontend/src/main.js:45)

**影响**

- 设置页可能出现组件未解析
- 即便能渲染，也可能缺少正确样式
- 这说明当前“按需手动注册”没有形成自检机制，后续页面继续加组件时还会重复踩坑

**建议优先级**

P1。

---

### 3. `/settings` 接口存在“展示可配、实际不可配”的设计不一致

**结论**

后端把 `knowledge_base_dir` 和 `model_name` 作为运行时设置返回给前端，但更新接口根本不接受这两个字段，实际只是把当前值重新写回数据库。接口表达与真实能力不一致。

**证据**

返回模型包含：

- `knowledge_base_dir`
- `model_name`

见：

- [settings.py](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Backend/app/schemas/settings.py:10)
- [settings.py](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Backend/app/schemas/settings.py:16)

但更新请求模型只允许更新 3 个数值字段：

- [settings.py](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Backend/app/schemas/settings.py:18)

同时，更新逻辑会把 `knowledge_base_dir` 和 `model_name` 原样写回，而不是接收用户输入：

- [settings.py](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Backend/app/api/routes/settings.py:62)
- [settings.py](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Backend/app/api/routes/settings.py:67)
- [settings.py](/D:/GitHub_repo/00_active\webui-autotest-agent/AutoTest_Backend/app/api/routes/settings.py:68)

**问题本质**

- 接口语义不清
- 前端以后如果暴露更多设置项，会误以为后端支持持久化修改
- 数据库里看起来像“保存成功”，但实际上没有配置变更能力

**建议优先级**

P1。

---

### 4. RAG 词表和测试样例存在明显编码污染

**结论**

RAG 相关代码和测试文件里已经出现大面积中文乱码（mojibake），这不是纯显示问题，因为这些文本本身就是检索扩展词、source hint 和测试样例的一部分。

**证据**

业务代码中的中文别名已经是乱码文本：

- [rag_service.py](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Backend/app/services/rag_service.py:17)
- [rag_service.py](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Backend/app/services/rag_service.py:23)
- [rag_service.py](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Backend/app/services/rag_service.py:52)

测试样例同样被编码污染：

- [test_rag_service.py](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Backend/tests/test_rag_service.py:18)
- [test_rag_service.py](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Backend/tests/test_rag_service.py:45)
- [test_rag_service.py](/D:/GitHub_repo/00_active/webui-autotest-agent/AutoTest_Backend/tests/test_rag_service.py:72)

**影响**

- 中文 query expansion 命中质量会下降
- 测试样例即使“能跑”，也已经失去可读性和可信度
- 后续维护者无法判断这些词条是否还是原始语义

**建议优先级**

P1。

---

## 观察到的工程风险

### 5. 测试链路不稳定，当前无法形成可靠的一键验收

**观察**

- 后端全量测试在当前环境下未能顺利跑完，执行到数据库迁移测试时发生长时间卡住
- 但我把 `initialize_database()` 单独抽出来做最小化验证时，它本身是可以正常完成的
- 前端测试脚本在当前环境中也没有稳定产出结果

**这说明什么**

这里不能简单下结论说“数据库迁移逻辑就是错的”。更合理的判断是：

- 当前测试基建还不稳定
- 至少存在环境依赖、测试隔离、路径/权限或执行脚本层面的额外问题
- 项目现在还达不到“新人拉下来就能稳定自证”的状态

**影响**

- 难以支撑持续迭代
- 答辩时如果被要求现场验证，风险较高
- CI 接入前会先被测试稳定性拖垮

**建议优先级**

P2。

---

## 问题优先级建议

### 第一优先级

- 修掉前端 `run-build.mjs` 对 Vite 的侵入式 patch，恢复可正常构建
- 补齐前端实际使用到的 Element Plus 组件注册与样式

### 第二优先级

- 统一 `/settings` 接口语义：要么删掉伪配置字段，要么真正支持更新
- 清理 RAG 中文词表与测试样例中的编码污染，恢复语义可读性

### 第三优先级

- 稳定测试链路，至少做到本地可重复执行
- 给前后端分别补一条最小可验收命令，并保证能在 README 中真实执行

---

## 总结

这个仓库最大的问题不是“功能完全没做出来”，而是“工程闭环不够硬”：

- 构建不能稳定通过
- 页面和组件注册不一致
- 设置接口语义不一致
- 中文检索资产被编码污染
- 测试链路不能稳定证明系统可用

如果目标是毕业设计答辩加作品集，这几类问题必须优先处理。否则项目看起来功能很多，但一到“构建、验证、解释设计一致性”这几个硬环节就会露短板。
