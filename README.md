# WebUI AutoTest Agent

An AI-powered web UI test automation platform that generates, executes, and self-heals Selenium test scripts using LLM + RAG.

## Architecture

```text
webui-autotest-agent/
├── AutoTest_Backend/    # FastAPI backend (Python 3.12+)
├── AutoTest_Frontend/   # Vue 3 + Element Plus frontend
├── vue-admin-template/  # Target SUT for testing
└── docs/                # Architecture docs & optimization audit
```

**Backend** — FastAPI application providing REST APIs for test case generation, execution, self-healing, and knowledge-base management. Uses ChromaDB for vector retrieval and OpenAI-compatible LLM for code generation/repair.

**Frontend** — Vue 3 SPA with Element Plus UI. Includes a workbench for prompt-driven test generation, execution history, metrics dashboard with trend charts, and system settings.

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 24+
- Chrome/Chromium + ChromeDriver
- An OpenAI-compatible API key (e.g. DeepSeek)

### Backend

```bash
cd AutoTest_Backend
pip install -e .           # or: uv sync
cp .env.example .env       # configure DEEPSEEK_API_KEY, paths
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd AutoTest_Frontend
npm install
npm run dev                # dev server on http://localhost:5173
```

### Target Application (SUT)

```bash
cd vue-admin-template
npm install
npm run dev                # dev server on http://localhost:9528
```

## Testing

### Backend (unittest)

```bash
cd AutoTest_Backend
python run_backend_tests.py
```

### Frontend (vitest)

```bash
cd AutoTest_Frontend
npm test
```

## Key Features

- **Prompt-driven generation** — Describe a test scenario in natural language (Chinese or English); the LLM generates a runnable Selenium script.
- **RAG-augmented context** — Knowledge base documents provide domain-specific patterns (login flows, search patterns, Element UI interactions) to improve generation quality.
- **Self-healing execution** — Failed scripts are automatically repaired using LLM-based analysis with strategy awareness (interaction-first vs. direct navigation).
- **Execution metrics** — Track first-pass success rate, self-heal trigger/success rates, and daily trend data.
- **Bilingual UI** — Full English and Chinese localization.

## API Overview

All endpoints are prefixed with `/api/v1`.

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/health` | System health check |
| POST | `/generate` | Generate test script from prompt |
| POST | `/executions` | Create and run an execution |
| GET | `/executions` | List executions (paginated) |
| GET | `/executions/stats` | Execution metrics and trends |
| GET | `/executions/{id}` | Get execution details |
| DELETE | `/executions/{id}` | Cancel an execution |
| GET | `/test-cases/{id}` | Get test case details |
| GET | `/settings` | Get runtime settings |
| PUT | `/settings` | Update runtime settings |
| POST | `/knowledge/rebuild` | Rebuild the knowledge index |

## CI

GitHub Actions runs backend tests and frontend tests + build on every push. See `.github/workflows/ci.yml`.

## License

This project is part of a graduation project and is not currently published under an open-source license.
