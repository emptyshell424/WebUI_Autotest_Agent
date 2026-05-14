# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**语言要求：所有回复必须使用中文。**

## Project overview

AI-powered web UI test automation platform: generate, execute, and self-heal Selenium scripts using LLM + RAG (ChromaDB). The target SUT is `vue-admin-template/` (Element UI admin panel).

## Commands

```bash
# Backend (Python 3.12+, pip/uv)
cd AutoTest_Backend
uvicorn app.main:app --reload --port 8000
python run_backend_tests.py                # run all backend tests
python -m pytest tests/test_generation_service.py -v   # single test file

# Frontend (Node 24+)
cd AutoTest_Frontend
npm run dev                                # dev server on :5173
npm test                                   # vitest

# Target SUT
cd vue-admin-template
npm run dev                                # dev server on :9528
```

## Architecture

```
AutoTest_Backend/
  app/main.py              FastAPI app factory (CORS, error handler, router mount)
  app/core/
    config.py              pydantic-settings → Settings (reads .env, case-sensitive)
    container.py           DI: plain ServiceContainer dataclass, lazy-init on request.app.state
    database.py            raw sqlite3 (no ORM) — 4 tables via executescript, column migration helpers
  app/api/
    router.py              mounts all sub-routers under /api/v1
    routes/                one module per feature (health, generate, executions, settings, knowledge, test_cases, agent)
  app/services/            all business logic
    llm_service.py         OpenAI-compatible client (DeepSeek default); system prompts, traceback parsing, repair prompt assembly
    generation_service.py  prompt → RAG + strategy context → LLM → cleaned code → DB record
    execution_service.py   subprocess runner with AST security validation, timeout, cancellation; self-heal loop (diagnose → repair → re-execute up to N attempts)
    rag_service.py         ChromaDB vector store + BM25 hybrid retrieval with query expansion, reranking; fallback to pure BM25 when ChromaDB unavailable
    strategy_service.py    interaction_first vs result_first strategy decisions for Baidu search scenarios; selector rules for vue-admin-template
    agent_orchestrator.py  ReAct loop: Thought → Action → Observation; streaming SSE events, multi-step plan support
    planner.py             generates ExecutionPlan for multi-step tasks
    task_analyzer.py       LLM-based task intent/classification
    agent_memory_service.py writes success/trap memory cards as Markdown to docs/knowledge/agent_memory/
    site_profile_service.py tracks per-site selector reliability patterns
    adaptive_strategy_service.py  selects optimal repair strategy based on failure diagnosis
    intelligent_diagnostic_service.py  LLM-based failure diagnosis
  app/tools/               agent-callable tools (BaseTool subclass + ToolRegistry)
    base.py                BaseTool, ToolRegistry, ToolResult
    generate_tool.py, execute_tool.py, repair_tool.py, diagnose_tool.py,
    validate_tool.py, knowledge_tool.py, memory_tool.py, dom_tool.py, screenshot_tool.py
  app/repositories/        raw-sql data access (TestCase, Execution, Settings repos)
  app/schemas/             Pydantic request/response models
  app/utils/
    code_parser.py         clean_code() — strip Markdown fences; extract_json() — robust JSON extraction

AutoTest_Frontend/src/
  main.js                  Vue 3 app, Pinia, Vue Router, Element Plus (on-demand tree-shaken)
  api/client.js            Axios client (60s timeout, localStorage baseUrl persistence)
  api/sse.js               POST-based SSE streaming via fetch + ReadableStream
  stores/                  Pinia stores (app: health/settings/stats; workspace: generate/execute/history; agent: SSE trace)
  views/                   WorkbenchView, HistoryView, MetricsView, SettingsView
  view-models/             pure formatting/classification functions (no Vue dependency)
  components/              CodeEditor (textarea + line numbers), TrendChart (SVG stacked bar), AgentTracePanel (timeline)
  i18n/index.js            custom lightweight i18n (en + zh-CN), ~500 lines, no vue-i18n dependency
  router/index.js          flat 4-route structure, lazy-loaded, HTML5 history mode
```

## Key patterns

### Dependency injection
`ServiceContainer` is a plain `@dataclass(slots=True)` holding all services/repos. Created lazily by `get_container(request)` → stored on `request.app.state.container`. Route handlers call `get_container(request)` to access dependencies. No DI framework.

### Database
Raw sqlite3 via `get_connection()` context manager (auto-commit on success). Schema defined in `initialize_database()` with an `_ensure_columns()` migration helper. Foreign keys enabled? No — referential integrity is enforced at the application layer only.

### LLM calls
All go through `LLMService._complete()` which creates `OpenAI` client with configurable `base_url`. Agent chat uses `agent_chat()` (system + user → raw string, caller parses JSON). Code generation uses `chat()` which prepends the strategy context. Repairs use `repair_script()` with structured failure context.

### Execution flow
1. `ExecutionService.create_execution()` → spawns `daemon=True` thread → `_run_execution_inner()`
2. AST-based security validation blocks unsafe imports/calls
3. Script runs as subprocess with timeout; stdout/stderr captured to files
4. On failure, self-heal loop: analyze repair strategy → diagnose failure → repair via LLM → re-execute
5. On heal success, writes agent memory card

### Agent (ReAct) loop
The newer agent path (`POST /api/v1/agent/run/stream`) runs an LLM-driven ReAct loop where the LLM selects tools dynamically. The orchestrator emits SSE events (thinking, action, observation, error, finish). Tools are wired from the DI container and registered in a `ToolRegistry`. Task analysis and planning happen before the ReAct loop starts.

### Strategy system
Two strategies: `interaction_first` (preserve page interaction flow) and `result_first` (direct results URL allowed). Strategy service decides based on prompt analysis (Baidu search heuristics). During self-heal, strategy can downgrade from interaction_first → result_first if homepage anchors fail.

### Retrieval modes
`vector` (ChromaDB only), `hybrid` (vector + BM25), `hybrid_rerank` (hybrid + re-ranking pass). Default is `hybrid_rerank`. When ChromaDB is unavailable, falls back to BM25-only.

### Selenium selector rules for vue-admin-template
Hard-coded critical selector rules in `strategy_service.py` (also in knowledge docs). Key gotcha: login button is `button.el-button--primary` NOT `button[type='submit']` because Element UI `<el-button>` renders `type="button"`.
