from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.services.rag_service import RAGService


EVAL_QUERIES = [
    {
        "query": "打开登录页面，输入用户名 admin 和密码 111111，并验证进入 Dashboard 页面。",
        "expected_source": "login_flows.md",
    },
    {
        "query": "进入 Form 页面，填写 Activity name，然后点击 Create 按钮。",
        "expected_source": "vue_admin_template_patterns.md",
    },
    {
        "query": "生成安全的测试脚本，可以使用 quote_plus，但不要导入 sys 或 os。",
        "expected_source": "safe_code_generation_rules.md",
    },
    {
        "query": "点击登录按钮后，验证进入首页。",
        "expected_source": "bilingual_ui_prompt_patterns.md",
    },
    {
        "query": "打开百度，搜索 DeepSeek，等待结果页面出现，然后打印测试完成。",
        "expected_source": "search_flows.md",
    },
    {
        "query": "百度首页搜索框 kw 超时，TimeoutException，找不到输入框。",
        "expected_source": "search_flows.md",
    },
]


def evaluate_mode(rag: RAGService, mode: str) -> dict[str, object]:
    hits_at_1 = 0
    hits_at_3 = 0
    rows: list[dict[str, object]] = []

    for sample in EVAL_QUERIES:
        result = rag.search(sample["query"], retrieval_mode=mode, n_results=3)
        sources = result.sources
        expected = sample["expected_source"]
        hit_at_1 = bool(sources and sources[0] == expected)
        hit_at_3 = expected in sources
        hits_at_1 += int(hit_at_1)
        hits_at_3 += int(hit_at_3)
        rows.append(
            {
                "query": sample["query"],
                "expected_source": expected,
                "retrieved_sources": sources,
                "hit_at_1": hit_at_1,
                "hit_at_3": hit_at_3,
            }
        )

    total = len(EVAL_QUERIES)
    return {
        "mode": mode,
        "total_queries": total,
        "recall_at_1": round(hits_at_1 / total, 4),
        "recall_at_3": round(hits_at_3 / total, 4),
        "details": rows,
    }


def main() -> None:
    backend_root = Path(__file__).resolve().parent
    settings = Settings(
        SQLITE_DB_PATH=str(backend_root / "data" / "app.db"),
        VECTOR_STORE_DIR=str(backend_root / "data" / "rag"),
        KNOWLEDGE_BASE_DIR=str(backend_root / "docs" / "knowledge"),
        EXECUTIONS_DIR=str(backend_root / "runs"),
    )
    rag = RAGService(settings)
    rag.rebuild_index()

    report = {
        "vector": evaluate_mode(rag, "vector"),
        "hybrid": evaluate_mode(rag, "hybrid"),
        "hybrid_rerank": evaluate_mode(rag, "hybrid_rerank"),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
