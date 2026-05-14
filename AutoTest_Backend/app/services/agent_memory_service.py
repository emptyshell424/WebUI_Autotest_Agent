from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.models import ExecutionRecord, SelfHealAttemptRecord, TestCaseRecord

try:
    import chromadb  # type: ignore
except ModuleNotFoundError:
    chromadb = None

logger = logging.getLogger("autotest.agent_memory")

MEMORY_COLLECTION_NAME = "agent_memory"


@dataclass(frozen=True, slots=True)
class MemorySearchResult:
    """Result from searching agent memory."""
    cards: list[dict[str, Any]]
    context: str  # concatenated text for LLM injection
    result_count: int


class AgentMemoryService:
    """Persist and retrieve agent learning experiences.

    Write path (existing):  Markdown files in knowledge_base_dir/agent_memory/
    Read path: ChromaDB `agent_memory` collection for similarity search.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def write_healed_memory(
        self,
        *,
        execution: ExecutionRecord,
        test_case: TestCaseRecord,
        attempt: SelfHealAttemptRecord,
    ) -> Path:
        self.settings.agent_memory_dir.mkdir(parents=True, exist_ok=True)
        target = self.settings.agent_memory_dir / f"{execution.id}.md"
        target.write_text(
            self.build_memory_card(execution=execution, test_case=test_case, attempt=attempt),
            encoding="utf-8",
        )
        return target

    def build_memory_card(
        self,
        *,
        execution: ExecutionRecord,
        test_case: TestCaseRecord,
        attempt: SelfHealAttemptRecord,
    ) -> str:
        repaired_code = attempt.repaired_code or execution.executed_code
        stable_selectors = self._extract_stable_selectors(repaired_code)
        validation_rules = self._extract_validation_rules(
            repaired_code=repaired_code,
            logs=execution.logs or attempt.logs,
        )
        keywords = self._keywords(
            test_case.prompt,
            attempt.failure_type,
            attempt.failure_signal,
            stable_selectors,
        )

        return "\n".join(
            [
                f"# Agent Memory: {self._single_line(test_case.title or test_case.prompt, 100)}",
                "",
                f"Keywords: {', '.join(keywords)}.",
                "",
                "## 场景",
                self._text_or_default(test_case.prompt, "未记录原始场景。"),
                "",
                "## 失败类型",
                self._text_or_default(attempt.failure_type, "unknown_failure"),
                "",
                "## 失败信号",
                self._text_or_default(attempt.failure_signal or attempt.failure_reason, "未记录失败信号。"),
                "",
                "## 根因",
                self._text_or_default(attempt.suspected_root_cause, "修复成功但未记录明确根因。"),
                "",
                "## 修复动作",
                self._text_or_default(attempt.repair_summary or attempt.repair_hint, "使用修复后的 Selenium 脚本重新执行并通过。"),
                "",
                "## 稳定选择器",
                self._bullet_list(stable_selectors, "未从修复代码中提取到明确选择器；优先复用修复代码中的稳定页面锚点。"),
                "",
                "## 验证规则",
                self._bullet_list(validation_rules, "修复脚本执行状态为 completed。"),
                "",
                "## 执行元数据",
                f"- execution_id: `{execution.id}`",
                f"- attempt_number: `{attempt.attempt_number}`",
                f"- strategy_before: `{attempt.strategy_before}`",
                f"- strategy_after: `{attempt.strategy_after}`",
                f"- site_profile: `{attempt.site_profile or execution.site_profile or 'unknown'}`",
                "",
            ]
        )

    def _extract_stable_selectors(self, code: str) -> list[str]:
        selectors: list[str] = []
        by_patterns = [
            r"By\.([A-Z_]+)\s*,\s*['\"]([^'\"]+)['\"]",
            r"find_element\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
            r"find_elements\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
        ]
        for pattern in by_patterns:
            for match in re.finditer(pattern, code):
                selectors.append(f"{match.group(1)}={match.group(2)}")
        for match in re.finditer(r"https?://[^\s'\"）)]+", code):
            selectors.append(f"url={match.group(0)}")
        return self._dedupe([self._single_line(item, 160) for item in selectors])

    def _extract_validation_rules(self, *, repaired_code: str, logs: str | None) -> list[str]:
        rules: list[str] = []
        for line in repaired_code.splitlines():
            stripped = line.strip()
            if stripped.startswith("assert "):
                rules.append(stripped)
            elif "WebDriverWait" in stripped and "until" in stripped:
                rules.append(stripped)
            elif "print(" in stripped and "Test Completed" in stripped:
                rules.append("print `Test Completed` only after assertions pass")
        if logs and "Test Completed" in logs:
            rules.append("runtime log contains `Test Completed`")
        rules.append("repair attempt status is `completed`")
        return self._dedupe([self._single_line(item, 180) for item in rules])

    _KEYWORD_STOPWORDS: set[str] = {
        "the", "for", "is", "to", "and", "then", "open", "wait", "page",
        "last", "most", "recent", "call", "than", "that", "with", "from",
        "this", "into", "after", "when", "will", "not", "are", "was", "has",
        "its", "over", "each", "next", "once", "also", "very", "just", "can",
        "new", "now", "one", "two", "all", "any", "get", "set", "use", "had",
        "been", "were", "they", "have", "more", "some", "only", "what", "how",
        "which", "your", "first", "before", "after", "above", "below", "an",
        "or", "but", "so", "if", "no", "on", "at", "by", "be", "as", "do",
        "in", "it", "of", "up", "out", "off", "our", "you", "we", "he", "she",
    }

    def _keywords(
        self,
        prompt: str,
        failure_type: str | None,
        failure_signal: str | None,
        selectors: list[str],
    ) -> list[str]:
        raw = [
            "agent_memory",
            "self-heal",
            "healed_completed",
            failure_type or "",
            failure_signal or "",
            prompt,
            *selectors,
        ]
        tokens: list[str] = []
        for item in raw:
            tokens.extend(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_#./:=!-]{2,}", item))
        filtered = [
            t for t in tokens
            if t.lower() not in self._KEYWORD_STOPWORDS and len(t) > 2
        ]
        return self._dedupe(filtered)[:30]

    def _bullet_list(self, items: list[str], fallback: str) -> str:
        values = items or [fallback]
        return "\n".join(f"- {item}" for item in values)

    def _text_or_default(self, value: str | None, default: str) -> str:
        cleaned = (value or "").strip()
        return cleaned if cleaned else default

    def _single_line(self, value: str, limit: int) -> str:
        cleaned = re.sub(r"\s+", " ", value).strip()
        return cleaned[: limit - 3] + "..." if len(cleaned) > limit else cleaned

    def _dedupe(self, values: list[str]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            key = normalized.lower()
            if normalized and key not in seen:
                seen.add(key)
                output.append(normalized)
        return output

    # ------------------------------------------------------------------
    # ChromaDB read / retrieval
    # ------------------------------------------------------------------

    def _get_chroma_client(self):
        """Return the ChromaDB client, or None if unavailable."""
        if chromadb is None:
            return None
        return chromadb.PersistentClient(path=str(self.settings.vector_store_dir))

    def _get_memory_collection(self):
        """Get or create the agent_memory ChromaDB collection."""
        client = self._get_chroma_client()
        if client is None:
            return None
        return client.get_or_create_collection(name=MEMORY_COLLECTION_NAME)

    def rebuild_memory_index(self) -> dict[str, Any]:
        """Index all agent_memory/*.md files into the ChromaDB collection."""
        memory_dir = self.settings.agent_memory_dir
        if not memory_dir.exists():
            return {"indexed": 0, "collection": MEMORY_COLLECTION_NAME}

        files = sorted(memory_dir.glob("*.md"))
        documents: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, str]] = []

        for fp in files:
            text = fp.read_text(encoding="utf-8").strip()
            if not text:
                continue
            doc_id = f"mem_{fp.stem}"
            card_type = self._detect_card_type(text)
            documents.append(text)
            ids.append(doc_id)
            metadatas.append({
                "source": fp.name,
                "card_type": card_type,
            })

        collection = self._get_memory_collection()
        if collection is not None and documents:
            collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
            logger.info("Indexed %d memory cards into %s", len(documents), MEMORY_COLLECTION_NAME)

        return {
            "indexed": len(documents),
            "collection": MEMORY_COLLECTION_NAME,
        }

    def search_similar(
        self,
        query: str,
        n_results: int = 3,
        card_type: str | None = None,
    ) -> MemorySearchResult:
        """Search the agent_memory ChromaDB collection for similar experiences.

        Args:
            query: natural-language description of the current situation.
            n_results: max number of memory cards to return.
            card_type: optional filter — 'heal', 'success', or 'trap'.

        Returns:
            MemorySearchResult with matching cards and a context string.
        """
        collection = self._get_memory_collection()
        if collection is None or collection.count() == 0:
            # Try to build the index if the collection is empty
            self.rebuild_memory_index()
            collection = self._get_memory_collection()
            if collection is None or collection.count() == 0:
                return MemorySearchResult(cards=[], context="", result_count=0)

        where_filter = {"card_type": card_type} if card_type else None
        try:
            results = collection.query(
                query_texts=[query],
                n_results=min(n_results, collection.count()),
                where=where_filter,
            )
        except Exception:
            logger.warning("Memory search failed", exc_info=True)
            return MemorySearchResult(cards=[], context="", result_count=0)

        cards: list[dict[str, Any]] = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, doc in enumerate(docs):
            meta = metas[i] if i < len(metas) else {}
            dist = distances[i] if i < len(distances) else 0.0
            cards.append({
                "content": doc,
                "source": meta.get("source", ""),
                "card_type": meta.get("card_type", "unknown"),
                "distance": dist,
            })

        context = "\n\n---\n\n".join(c["content"][:2000] for c in cards)
        return MemorySearchResult(
            cards=cards,
            context=context,
            result_count=len(cards),
        )

    # ------------------------------------------------------------------
    # Success pattern & known trap cards
    # ------------------------------------------------------------------

    def write_success_memory(
        self,
        *,
        prompt: str,
        code: str,
        execution_id: str,
    ) -> Path:
        """Write a 'success pattern' card when a test passes on the first try."""
        self.settings.agent_memory_dir.mkdir(parents=True, exist_ok=True)
        selectors = self._extract_stable_selectors(code)
        keywords = self._keywords(prompt, "first_success", None, selectors)
        card = "\n".join([
            f"# Success Pattern: {self._single_line(prompt, 100)}",
            "",
            f"Keywords: {', '.join(keywords)}.",
            "",
            "## 场景",
            prompt,
            "",
            "## 成功策略",
            "首次执行即通过，以下脚本和选择器经验证稳定。",
            "",
            "## 稳定选择器",
            self._bullet_list(selectors, "无显式选择器。"),
            "",
            "## 执行元数据",
            f"- execution_id: `{execution_id}`",
            f"- card_type: `success`",
            "",
        ])
        target = self.settings.agent_memory_dir / f"success_{execution_id}.md"
        target.write_text(card, encoding="utf-8")
        self._index_single_card(target, card, "success")
        return target

    def write_trap_memory(
        self,
        *,
        prompt: str,
        error_summary: str,
        execution_id: str,
        attempt_count: int,
    ) -> Path:
        """Write a 'known trap' card when a test fails repeatedly."""
        self.settings.agent_memory_dir.mkdir(parents=True, exist_ok=True)
        keywords = self._keywords(prompt, "known_trap", error_summary, [])
        card = "\n".join([
            f"# Known Trap: {self._single_line(prompt, 100)}",
            "",
            f"Keywords: {', '.join(keywords)}.",
            "",
            "## 场景",
            prompt,
            "",
            "## 反复失败摘要",
            error_summary[:1000],
            "",
            "## 建议",
            f"此场景在 {attempt_count} 次尝试后仍未通过，建议人工检查或调整策略。",
            "",
            "## 执行元数据",
            f"- execution_id: `{execution_id}`",
            f"- attempt_count: `{attempt_count}`",
            f"- card_type: `trap`",
            "",
        ])
        target = self.settings.agent_memory_dir / f"trap_{execution_id}.md"
        target.write_text(card, encoding="utf-8")
        self._index_single_card(target, card, "trap")
        return target

    def _index_single_card(self, path: Path, content: str, card_type: str) -> None:
        """Index a single memory card into ChromaDB immediately after writing."""
        collection = self._get_memory_collection()
        if collection is None:
            return
        doc_id = f"mem_{path.stem}"
        try:
            collection.upsert(
                documents=[content],
                ids=[doc_id],
                metadatas=[{"source": path.name, "card_type": card_type}],
            )
        except Exception:
            logger.warning("Failed to index memory card %s", doc_id, exc_info=True)

    @staticmethod
    def _detect_card_type(text: str) -> str:
        """Detect card type from the memory card content."""
        lower = text[:200].lower()
        if "success pattern" in lower or "card_type: `success`" in lower:
            return "success"
        if "known trap" in lower or "card_type: `trap`" in lower:
            return "trap"
        return "heal"
