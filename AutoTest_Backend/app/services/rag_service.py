from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings

logger = logging.getLogger("autotest.rag")

try:
    import chromadb  # type: ignore
except ModuleNotFoundError:
    chromadb = None


TERM_ALIASES = {
    "login": ["登录", "登入", "登陆", "login", "sign in", "log in"],
    "dashboard": ["dashboard", "首页", "后台首页", "控制台"],
    "table": ["表格", "table"],
    "form": ["表单", "form"],
    "create": ["创建", "新建", "提交", "create"],
    "search": ["搜索", "搜寻", "检索", "查询", "search"],
    "search_input": [
        "搜索框",
        "search input",
        "keyword input",
        "kw",
        "input[name='wd']",
        'input[name="wd"]',
        "关键词输入框",
    ],
    "baidu": ["百度", "baidu", "百度首页"],
    "results_page": [
        "结果页",
        "结果页面",
        "搜索结果",
        "results page",
        "result container",
        "stable results container",
        "#content_left",
        "结果区域",
        "结果容器",
    ],
    "verify": ["验证", "断言", "校验", "assert", "verify", "check"],
    "message": ["提示", "消息", "toast", "success text", "feedback"],
    "click": ["点击", "单击", "click", "button", "submit"],
    "input": ["输入", "填写", "键入", "input", "send_keys", "placeholder"],
    "wait": ["等待", "wait", "explicit wait", "visibility", "clickable", "loading"],
    "safe": ["安全", "safe", "import", "minimal imports", "sys", "os", "subprocess", "pathlib"],
    "print_completed": ["打印", "测试完成", "Test Completed", "print success"],
    "homepage_search": [
        "从首页开始",
        "首页搜索框",
        "在首页搜索框输入",
        "点击搜索按钮",
        "模拟用户输入",
        "homepage search box",
        "首页交互流程",
    ],
    "homepage_timeout": [
        "TimeoutException",
        "timeout",
        "search input timeout",
        "首页搜索框超时",
        "找不到#kw",
        "找不到kw",
    ],
}

CANONICAL_EXPANSIONS = {
    "login": ["username", "password", "dashboard", "post login", "admin"],
    "dashboard": ["name admin", "post login anchor", "home page"],
    "table": ["example table", "title", "author", "pageviews", "status", "table header", "element ui table"],
    "form": ["activity name", "activity zone", "create", "submit", "element ui form"],
    "create": ["submit", "success message", "button"],
    "search": [
        "keyword",
        "search input",
        "result container",
        "results",
        "baidu search homepage",
        "interaction first",
    ],
    "search_input": ["search input", "keyword input", "input", "query field", "kw", "input[name='wd']"],
    "baidu": ["baidu home page", "results", "result container", "baidu.com/s?wd=", "baidu search"],
    "results_page": [
        "results page",
        "result container",
        "search results",
        "stable results container",
        "#content_left",
    ],
    "verify": ["assert", "verify", "visible text", "result anchor", "stable assertion"],
    "message": ["toast", "success text", "feedback"],
    "click": ["button", "click", "submit", "element_to_be_clickable"],
    "input": ["input", "send_keys", "field", "placeholder"],
    "wait": ["explicit wait", "visibility", "clickable", "loading"],
    "safe": ["safe import", "avoid sys", "avoid os", "avoid subprocess", "minimal imports"],
    "print_completed": ["print", "Test Completed", "success print after assertion"],
    "homepage_search": ["homepage search input", "#kw", "input[name='wd']", "homepage interaction flow"],
    "homepage_timeout": ["TimeoutException", "timeout", "homepage search anchor timeout", "kw", "input[name='wd']"],
}


def _build_query_expansion_rules() -> dict[str, list[str]]:
    rules: dict[str, list[str]] = {}
    for canonical, aliases in TERM_ALIASES.items():
        expansions = CANONICAL_EXPANSIONS.get(canonical, [])
        for alias in aliases:
            rules[alias] = expansions
    return rules


QUERY_EXPANSION_RULES = _build_query_expansion_rules()

SOURCE_HINTS = {
    "login_flows": TERM_ALIASES["login"]
    + TERM_ALIASES["dashboard"]
    + ["username", "password", "dashboard", "/login", "admin"],
    "vue_admin_template_patterns": [
        "vue-admin-template",
        "dashboard",
        "table",
        "form",
        "create",
        "submit",
        "name admin",
        "example",
        "example/table",
        "title",
        "author",
        "pageviews",
        "status",
    ]
    + TERM_ALIASES["login"]
    + TERM_ALIASES["table"]
    + TERM_ALIASES["form"],
    "safe_code_generation_rules": TERM_ALIASES["safe"],
    "bilingual_ui_prompt_patterns": TERM_ALIASES["login"]
    + TERM_ALIASES["search"]
    + TERM_ALIASES["click"]
    + TERM_ALIASES["verify"]
    + TERM_ALIASES["message"]
    + TERM_ALIASES["table"]
    + TERM_ALIASES["form"]
    + ["中文", "english"],
    "element_ui_form_table_patterns": TERM_ALIASES["form"]
    + TERM_ALIASES["table"]
    + TERM_ALIASES["create"]
    + TERM_ALIASES["message"]
    + ["element ui", "activity name", "activity zone", "el-table", "table header"],
    "search_flows": TERM_ALIASES["search"]
    + TERM_ALIASES["search_input"]
    + TERM_ALIASES["baidu"]
    + TERM_ALIASES["results_page"]
    + TERM_ALIASES["print_completed"]
    + TERM_ALIASES["homepage_search"]
    + TERM_ALIASES["homepage_timeout"],
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "be",
    "button",
    "by",
    "for",
    "http",
    "https",
    "in",
    "into",
    "is",
    "of",
    "on",
    "open",
    "page",
    "the",
    "then",
    "to",
    "url",
    "with",
}


@dataclass(slots=True)
class RAGSearchResult:
    context: str
    sources: list[str]
    result_count: int
    retrieval_mode: str


@dataclass(slots=True)
class RAGDocument:
    document: str
    source: str
    source_stem: str
    tokens: tuple[str, ...]


@dataclass(slots=True)
class HybridCandidate:
    candidate: RAGDocument
    vector_rank: int | None = None
    vector_score: float = 0.0
    bm25_score: float = 0.0
    hybrid_score: float = 0.0


class RAGService:
    collection_name = "selenium_knowledge"
    default_retrieval_mode = "hybrid_rerank"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._documents: list[RAGDocument] = []
        self._uses_vector_store = chromadb is not None
        self.client = (
            chromadb.PersistentClient(path=str(settings.vector_store_dir))
            if self._uses_vector_store
            else None
        )

    def rebuild_index(self) -> dict[str, int | str | bool]:
        files = self._knowledge_files()
        documents: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, str]] = []
        indexed_documents: list[RAGDocument] = []

        for file_path in files:
            source = file_path.relative_to(self.settings.knowledge_base_dir).as_posix()
            chunks = self._split_document(file_path.read_text(encoding="utf-8"), source=source)
            for index, chunk in enumerate(chunks):
                documents.append(chunk)
                ids.append(f"{re.sub(r'[^a-zA-Z0-9_.:-]+', '_', source)}-{index}")
                metadata = {"source": source, "source_stem": file_path.stem}
                metadatas.append(metadata)
                indexed_documents.append(
                    RAGDocument(
                        document=chunk,
                        source=source,
                        source_stem=file_path.stem,
                        tokens=tuple(self._tokenize_for_bm25(chunk)),
                    )
                )

        self._documents = indexed_documents

        if self._uses_vector_store:
            self._reset_collection()
            collection = self._get_collection()
            if documents:
                collection.upsert(documents=documents, ids=ids, metadatas=metadatas)

        return {
            "ready": bool(documents),
            "document_count": len(files),
            "chunk_count": len(documents),
            "collection_name": self.collection_name,
            "backend": "chromadb" if self._uses_vector_store else "fallback",
        }

    def search(
        self,
        query: str,
        n_results: int = 3,
        retrieval_mode: str | None = None,
    ) -> RAGSearchResult:
        normalized_query = query.strip()
        active_mode = self._normalize_retrieval_mode(retrieval_mode)
        if not normalized_query:
            return RAGSearchResult(
                context="",
                sources=[],
                result_count=0,
                retrieval_mode=active_mode,
            )

        if not self._documents:
            self.rebuild_index()

        augmented_query = self._build_search_query(normalized_query)

        if active_mode == "vector":
            return self._search_vector_only(augmented_query, n_results)
        if active_mode == "hybrid":
            return self._search_hybrid(augmented_query, n_results)
        return self._search_hybrid_rerank(augmented_query, n_results)

    def get_status(self) -> dict[str, int | str | bool]:
        if self._uses_vector_store:
            collection = self._get_collection()
            indexed_chunks = collection.count()
        else:
            if not self._documents:
                self.rebuild_index()
            indexed_chunks = len(self._documents)

        return {
            "ready": indexed_chunks > 0,
            "indexed_chunks": indexed_chunks,
            "document_count": len(self._knowledge_files()),
            "source_dir": str(self.settings.knowledge_base_dir),
            "collection_name": self.collection_name,
            "backend": "chromadb" if self._uses_vector_store else "fallback",
        }

    def _search_vector_only(self, augmented_query: str, n_results: int) -> RAGSearchResult:
        if self._uses_vector_store:
            collection = self._get_collection()
            collection_count = collection.count()
            if collection_count == 0:
                return self._build_search_result([], retrieval_mode="vector")
            results = collection.query(query_texts=[augmented_query], n_results=n_results)
            candidates = self._vector_candidates(results)
            return self._build_search_result(candidates[:n_results], retrieval_mode="vector")
        return self._search_bm25_only(augmented_query, n_results, retrieval_mode="vector")

    def _search_hybrid(self, augmented_query: str, n_results: int) -> RAGSearchResult:
        ranked_candidates = self._hybrid_candidates(augmented_query, n_results)
        selected = [item.candidate for item in ranked_candidates[:n_results]]
        return self._build_search_result(selected, retrieval_mode="hybrid")

    def _search_hybrid_rerank(self, augmented_query: str, n_results: int) -> RAGSearchResult:
        ranked_candidates = self._hybrid_candidates(augmented_query, n_results)
        selected = [item.candidate for item in ranked_candidates[: max(n_results * 2, n_results)]]
        return self._rerank_candidates(
            augmented_query,
            selected,
            n_results=n_results,
            retrieval_mode="hybrid_rerank",
        )

    def _search_bm25_only(
        self,
        augmented_query: str,
        n_results: int,
        *,
        retrieval_mode: str,
    ) -> RAGSearchResult:
        query_tokens = self._tokenize_for_bm25(augmented_query)
        scored: list[tuple[float, RAGDocument]] = []
        for candidate in self._documents:
            score = self._bm25_score(candidate.tokens, query_tokens)
            if score <= 0:
                continue
            scored.append((score, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [candidate for _, candidate in scored[:n_results]]
        return self._build_search_result(selected, retrieval_mode=retrieval_mode)

    def _hybrid_candidates(self, augmented_query: str, n_results: int) -> list[HybridCandidate]:
        query_tokens = self._tokenize_for_bm25(augmented_query)
        candidate_map: dict[str, HybridCandidate] = {}

        if self._uses_vector_store:
            collection = self._get_collection()
            collection_count = collection.count()
            if collection_count > 0:
                candidate_limit = min(max(n_results * 4, 8), max(collection_count, n_results))
                results = collection.query(query_texts=[augmented_query], n_results=candidate_limit)
                for rank_index, candidate in enumerate(self._vector_candidates(results)):
                    candidate_map[candidate.source] = HybridCandidate(
                        candidate=candidate,
                        vector_rank=rank_index,
                        vector_score=1.0 / (rank_index + 1),
                    )

        for candidate in self._documents:
            bm25_score = self._bm25_score(candidate.tokens, query_tokens)
            if bm25_score <= 0 and candidate.source not in candidate_map:
                continue
            hybrid_candidate = candidate_map.setdefault(candidate.source, HybridCandidate(candidate=candidate))
            hybrid_candidate.bm25_score = bm25_score

        max_bm25 = max((item.bm25_score for item in candidate_map.values()), default=0.0)
        normalized_query = self._normalize_text(augmented_query)
        for item in candidate_map.values():
            normalized_bm25 = item.bm25_score / max_bm25 if max_bm25 > 0 else 0.0
            source_signal = min(self._source_boost(item.candidate.source_stem, normalized_query) / 12, 1.0)
            item.hybrid_score = (
                0.45 * item.vector_score
                + 0.35 * normalized_bm25
                + 0.20 * source_signal
            )

        ranked = sorted(
            candidate_map.values(),
            key=lambda item: (
                -item.hybrid_score,
                item.vector_rank if item.vector_rank is not None else 10**6,
                item.candidate.source,
            ),
        )
        return ranked

    def _rerank_candidates(
        self,
        augmented_query: str,
        candidates: list[RAGDocument],
        *,
        n_results: int,
        retrieval_mode: str,
    ) -> RAGSearchResult:
        if not candidates:
            return self._build_search_result([], retrieval_mode=retrieval_mode)

        normalized_augmented_query = self._normalize_text(augmented_query)
        terms = self._search_terms(augmented_query)
        ranked: list[tuple[int, int, RAGDocument]] = []

        for index, candidate in enumerate(candidates):
            score = self._candidate_score(candidate, normalized_augmented_query, terms, index)
            ranked.append((score, index, candidate))

        ranked.sort(key=lambda item: (-item[0], item[1]))

        best_per_source: list[RAGDocument] = []
        seen_sources: set[str] = set()
        for _, _, candidate in ranked:
            if candidate.source in seen_sources:
                continue
            seen_sources.add(candidate.source)
            best_per_source.append(candidate)

        selected = best_per_source[:n_results]

        if len(selected) < n_results:
            for _, _, candidate in ranked:
                if candidate in selected:
                    continue
                selected.append(candidate)
                if len(selected) == n_results:
                    break

        return self._build_search_result(selected, retrieval_mode=retrieval_mode)

    def _candidate_score(
        self,
        candidate: RAGDocument,
        normalized_augmented_query: str,
        terms: list[str],
        rank_index: int,
    ) -> int:
        document_text = self._normalize_text(candidate.document)
        score = max(0, 4 - rank_index)

        for term in terms:
            term_hits = document_text.count(term)
            if term_hits:
                score += min(term_hits, 4)
                if len(term) >= 6:
                    score += 1

        score += self._source_boost(candidate.source_stem, normalized_augmented_query)
        if candidate.document.startswith("Keywords:"):
            score -= 3
        if len(candidate.document) >= 120:
            score += 2
        return score

    def _source_boost(self, source_stem: str, normalized_augmented_query: str) -> int:
        hints = SOURCE_HINTS.get(source_stem, [])
        boost = 0
        for hint in hints:
            normalized_hint = self._normalize_text(hint)
            if normalized_hint and normalized_hint in normalized_augmented_query:
                boost += 3
        return boost

    def _build_search_query(self, query: str) -> str:
        expanded_terms = [query.strip()]
        normalized_query = query.lower()
        if self._contains_chinese(query):
            expanded_terms.extend([
                "selenium ui test",
                "explicit wait",
                "stable assertion",
                "minimal imports",
            ])
        for trigger, expansions in QUERY_EXPANSION_RULES.items():
            if trigger.lower() in normalized_query:
                expanded_terms.extend(expansions)
        return " ".join(self._dedupe_preserve_order(expanded_terms))

    def _search_terms(self, text: str) -> list[str]:
        tokens = self._tokenize_for_bm25(text)
        filtered: list[str] = []
        for token in tokens:
            if self._contains_chinese(token):
                filtered.append(token)
                continue
            if len(token) >= 3 and token not in STOPWORDS:
                filtered.append(token)
        return self._dedupe_preserve_order(filtered)

    def _normalize_text(self, text: str) -> str:
        lowered = text.lower()
        return re.sub(r"[^a-z0-9\u4e00-\u9fff#:=./!\-]+", " ", lowered)

    def _contains_chinese(self, text: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", text))

    def _dedupe_preserve_order(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for item in items:
            value = item.strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            output.append(item.strip())
        return output

    def _vector_candidates(self, results: dict) -> list[RAGDocument]:
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        candidates: list[RAGDocument] = []
        for index, document in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            source = str((metadata or {}).get("source", "unknown"))
            source_stem = str((metadata or {}).get("source_stem", Path(source).stem))
            candidates.append(
                RAGDocument(
                    document=document,
                    source=source,
                    source_stem=source_stem,
                    tokens=tuple(self._tokenize_for_bm25(document)),
                )
            )
        return candidates

    def _tokenize_for_bm25(self, text: str) -> list[str]:
        normalized = self._normalize_text(text)
        tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9][a-z0-9:_./!#=-]*", normalized)
        return [token for token in tokens if self._contains_chinese(token) or token not in STOPWORDS]

    def _bm25_score(self, document_tokens: tuple[str, ...], query_tokens: list[str]) -> float:
        if not document_tokens or not query_tokens or not self._documents:
            return 0.0

        tf = Counter(document_tokens)
        doc_length = len(document_tokens)
        avgdl = sum(len(doc.tokens) for doc in self._documents) / len(self._documents)
        score = 0.0
        k1 = 1.5
        b = 0.75

        for token in query_tokens:
            freq = tf.get(token, 0)
            if freq == 0:
                continue
            doc_freq = sum(1 for doc in self._documents if token in doc.tokens)
            if doc_freq == 0:
                continue
            idf = math.log(1 + (len(self._documents) - doc_freq + 0.5) / (doc_freq + 0.5))
            numerator = freq * (k1 + 1)
            denominator = freq + k1 * (1 - b + b * (doc_length / max(avgdl, 1)))
            score += idf * (numerator / denominator)
        return score

    def _normalize_retrieval_mode(self, retrieval_mode: str | None) -> str:
        mode = (retrieval_mode or self.default_retrieval_mode).strip().lower()
        if mode not in {"vector", "hybrid", "hybrid_rerank"}:
            return self.default_retrieval_mode
        return mode

    def _build_search_result(
        self,
        candidates: list[RAGDocument],
        *,
        retrieval_mode: str,
    ) -> RAGSearchResult:
        return RAGSearchResult(
            context="\n\n".join(
                candidate.document.strip()
                for candidate in candidates
                if candidate.document.strip()
            ),
            sources=sorted({candidate.source for candidate in candidates}),
            result_count=len(candidates),
            retrieval_mode=retrieval_mode,
        )

    def _get_collection(self):
        if not self.client:
            raise RuntimeError("Vector store client is unavailable.")
        return self.client.get_or_create_collection(name=self.collection_name)

    def _reset_collection(self) -> None:
        if not self.client:
            return
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            logger.warning("Failed to delete collection %s, continuing", self.collection_name, exc_info=True)

    def _knowledge_files(self) -> list[Path]:
        if not self.settings.knowledge_base_dir.exists():
            return []
        files = sorted(self.settings.knowledge_base_dir.rglob("*.md"))
        files.extend(sorted(self.settings.knowledge_base_dir.rglob("*.txt")))
        return files

    def _split_document(self, text: str, *, source: str = "") -> list[str]:
        if source.startswith("agent_memory/"):
            stripped = text.strip()
            return [stripped] if stripped else []
        normalized = text.replace("\r\n", "\n")
        chunks = [chunk.strip() for chunk in normalized.split("\n\n") if chunk.strip()]
        if len(chunks) > 1 and chunks[0].startswith("Keywords:"):
            chunks = [f"{chunks[0]}\n\n{chunks[1]}", *chunks[2:]]
        if chunks:
            return chunks
        return [line.strip() for line in normalized.splitlines() if line.strip()]
