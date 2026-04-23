# Architecture Overview

## System Context

```text
┌─────────────┐     HTTP/JSON      ┌──────────────────┐    OpenAI API     ┌───────────┐
│  Vue 3 SPA  │ ◄────────────────► │  FastAPI Backend  │ ────────────────► │  LLM      │
│  (Browser)  │    /api/v1/*       │  (Python 3.12+)   │                   │  (DeepSeek)│
└─────────────┘                    └──────────────────┘                   └───────────┘
                                          │
                                   ┌──────┴──────┐
                                   │             │
                              ┌────▼───┐   ┌────▼────┐
                              │ SQLite │   │ChromaDB │
                              │  (DB)  │   │ (Vector)│
                              └────────┘   └─────────┘
```

## Backend Layer Diagram

```text
┌─ API Layer (FastAPI Routes) ──────────────────────────────────┐
│  health  │  generate  │  executions  │  settings  │ knowledge │
└──────────┴────────────┴──────────────┴────────────┴───────────┘
                              │
┌─ Service Layer ─────────────┴─────────────────────────────────┐
│  GenerationService  │  ExecutionService  │  StrategyService   │
│  RAGService         │  LLMService        │                    │
└─────────────────────┴────────────────────┴────────────────────┘
                              │
┌─ Repository Layer ──────────┴─────────────────────────────────┐
│  TestCaseRepository  │  ExecutionRepository  │ SystemSettings  │
└──────────────────────┴───────────────────────┴────────────────┘
                              │
┌─ Core Infrastructure ───────┴─────────────────────────────────┐
│  Config  │  Container (DI)  │  Database  │  Logger  │ Exceptions│
└──────────┴──────────────────┴────────────┴──────────┴──────────┘
```

## Frontend Layer Diagram

```text
┌─ Views ───────────────────────────────────────────────────────┐
│  WorkbenchView  │  HistoryView  │  MetricsView  │ SettingsView│
└────────┬────────┴───────┬───────┴───────┬───────┴─────┬───────┘
         │                │               │             │
┌─ Components ────────────┴───────────────┴─────────────┘
│  CodeEditor  │  TrendChart                            │
└──────────────┴────────────────────────────────────────┘
         │
┌─ View Models ─────────────────────────────────────────────────┐
│  workbench.js  │  history.js  │  metrics.js                   │
└────────────────┴──────────────┴───────────────────────────────┘
         │
┌─ Stores (Pinia) ─────────────────────────────────────────────┐
│  app.js (health, settings, stats)  │  workspace.js (workflow) │
└────────────────────────────────────┴──────────────────────────┘
         │
┌─ API Client (axios) ─────────────────────────────────────────┐
│  client.js — base URL management, response interceptor        │
└───────────────────────────────────────────────────────────────┘
```

## Core Workflows

### Test Generation Flow

```text
User prompt → POST /generate
  → GenerationService.generate()
    → StrategyService.analyze_generation(prompt)  // determine strategy
    → RAGService.search(prompt)                   // retrieve knowledge context
    → LLMService.generate_script(prompt, context) // LLM generates Python code
    → TestCaseRepository.create(...)              // persist test case
  ← GenerateResponse { case, knowledge_sources, retrieval_mode }
```

### Test Execution Flow

```text
POST /executions { test_case_id }
  → ExecutionService.create_execution()
    → ExecutionRepository.create(status="queued")
    → Background thread: _run_execution()
      → Write script to temp directory
      → subprocess.run(python, script)
      → If failed AND self_heal_attempts < limit:
        → StrategyService.analyze_repair(prompt, error)
        → LLMService.repair_script(code, error, context)
        → Re-execute repaired script
        → Repeat until success or limit reached
      → ExecutionRepository.mark_finished()
  ← ExecutionRead { id, status }
```

### RAG Retrieval Flow

```text
RAGService.search(query, retrieval_mode)
  → Normalize query (Chinese segmentation, alias expansion)
  → Vector search via ChromaDB
  → If hybrid: BM25 keyword search + merge results
  → If hybrid_rerank: re-rank merged results by combined score
  ← RAGResult { context, sources, result_count, retrieval_mode }
```

## Data Model

### SQLite Tables

| Table | Purpose |
| ----- | ------- |
| `test_case` | Generated test cases with prompt, code, RAG context |
| `execution_record` | Execution runs with status, logs, error, timing |
| `self_heal_attempt` | Individual repair attempts per execution |
| `system_setting` | Key-value runtime configuration |

### Key Relationships

```text
test_case  1 ──── N  execution_record  1 ──── N  self_heal_attempt
```

## Configuration

Environment variables are managed via `pydantic-settings` in `app/core/config.py`:

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `DEEPSEEK_API_KEY` | — | LLM API key (required for generation) |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | LLM endpoint |
| `MODEL_NAME` | `deepseek-chat` | Model identifier |
| `SQLITE_DB_PATH` | `data/app.db` | Database file path |
| `VECTOR_STORE_DIR` | `data/rag` | ChromaDB persistence directory |
| `KNOWLEDGE_BASE_DIR` | `docs/knowledge` | Markdown knowledge documents |
| `EXECUTIONS_DIR` | `runs` | Script execution working directory |
| `EXECUTION_TIMEOUT_SECONDS` | `120` | Per-execution timeout |
| `MAX_SELF_HEAL_ATTEMPTS` | `3` | Max repair retries |
| `MAX_CONCURRENT_EXECUTIONS` | `2` | Parallel execution limit |

## Testing Strategy

| Layer | Framework | Runner | Coverage |
| ----- | --------- | ------ | -------- |
| Backend unit/integration | unittest | `python run_backend_tests.py` | API endpoints, services, RAG quality |
| Frontend unit | Vitest + happy-dom | `npm test` | Stores, view-models, component rendering |
| Frontend build | Vite | `npm run build` | Compilation, tree-shaking |
| CI | GitHub Actions | `.github/workflows/ci.yml` | All of the above |

## Knowledge Base

Markdown documents in `docs/knowledge/` are indexed by the RAG service at startup and on rebuild. Each document follows the pattern:

```markdown
# Title

Keywords: keyword1, keyword2, 中文关键词.

English guidance paragraph.

中文指导段落。
```

The RAG system uses:

- **ChromaDB** for dense vector retrieval
- **BM25** for sparse keyword matching (with Chinese segmentation)
- **Hybrid rerank** mode that combines both and re-scores results
