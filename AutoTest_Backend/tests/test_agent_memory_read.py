"""Tests for AgentMemoryService read-path + SearchMemoryTool."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from . import _bootstrap  # noqa: F401 — path bootstrap

from app.services.agent_memory_service import (
    AgentMemoryService,
    MemorySearchResult,
    MEMORY_COLLECTION_NAME,
)
from app.tools.memory_tool import SearchMemoryTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(tmp_dir: Path):
    """Create a mock Settings pointing at *tmp_dir*."""
    settings = MagicMock()
    settings.agent_memory_dir = tmp_dir / "agent_memory"
    settings.vector_store_dir = tmp_dir / "vector_store"
    return settings


def _write_card(memory_dir: Path, filename: str, content: str) -> Path:
    """Write a memory card .md file to the memory directory."""
    memory_dir.mkdir(parents=True, exist_ok=True)
    fp = memory_dir / filename
    fp.write_text(content, encoding="utf-8")
    return fp


# ---------------------------------------------------------------------------
# MemorySearchResult dataclass
# ---------------------------------------------------------------------------


class MemorySearchResultTests(unittest.TestCase):
    def test_empty_result(self):
        r = MemorySearchResult(cards=[], context="", result_count=0)
        self.assertEqual(r.result_count, 0)
        self.assertEqual(r.cards, [])
        self.assertEqual(r.context, "")

    def test_populated_result(self):
        cards = [{"content": "card1", "source": "a.md", "card_type": "heal", "distance": 0.1}]
        r = MemorySearchResult(cards=cards, context="card1", result_count=1)
        self.assertEqual(r.result_count, 1)
        self.assertEqual(r.cards[0]["source"], "a.md")


# ---------------------------------------------------------------------------
# _detect_card_type
# ---------------------------------------------------------------------------


class DetectCardTypeTests(unittest.TestCase):
    def test_detect_heal(self):
        text = "# Agent Memory: some scenario\n## 失败类型\nselector_not_found"
        self.assertEqual(AgentMemoryService._detect_card_type(text), "heal")

    def test_detect_success(self):
        text = "# Success Pattern: open Baidu\nKeywords: ..."
        self.assertEqual(AgentMemoryService._detect_card_type(text), "success")

    def test_detect_success_by_metadata(self):
        text = "Some header\n- card_type: `success`\n"
        self.assertEqual(AgentMemoryService._detect_card_type(text), "success")

    def test_detect_trap(self):
        text = "# Known Trap: login fails\nKeywords: ..."
        self.assertEqual(AgentMemoryService._detect_card_type(text), "trap")

    def test_detect_trap_by_metadata(self):
        text = "Some header\n- card_type: `trap`\n"
        self.assertEqual(AgentMemoryService._detect_card_type(text), "trap")

    def test_default_to_heal(self):
        text = "Random content without known markers"
        self.assertEqual(AgentMemoryService._detect_card_type(text), "heal")


# ---------------------------------------------------------------------------
# write_success_memory
# ---------------------------------------------------------------------------


class WriteSuccessMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = _make_settings(self.tmp)
        self.svc = AgentMemoryService(self.settings)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_creates_file(self):
        path = self.svc.write_success_memory(
            prompt="打开百度搜索 Selenium",
            code="driver.find_element(By.ID, 'kw').send_keys('Selenium')",
            execution_id="exec-001",
        )
        self.assertTrue(path.exists())
        self.assertTrue(path.name.startswith("success_"))
        content = path.read_text(encoding="utf-8")
        self.assertIn("Success Pattern", content)
        self.assertIn("打开百度搜索 Selenium", content)
        self.assertIn("exec-001", content)
        self.assertIn("card_type: `success`", content)

    def test_contains_selectors(self):
        code = (
            "driver.find_element(By.ID, 'kw').send_keys('test')\n"
            "driver.find_element(By.CSS_SELECTOR, '#su').click()"
        )
        path = self.svc.write_success_memory(
            prompt="Search test", code=code, execution_id="exec-002",
        )
        content = path.read_text(encoding="utf-8")
        self.assertIn("ID=kw", content)

    def test_indexes_into_chromadb(self):
        with patch.object(self.svc, "_index_single_card") as mock_index:
            self.svc.write_success_memory(
                prompt="test", code="pass", execution_id="exec-003",
            )
            mock_index.assert_called_once()
            args = mock_index.call_args
            self.assertEqual(args[0][2], "success")  # card_type


# ---------------------------------------------------------------------------
# write_trap_memory
# ---------------------------------------------------------------------------


class WriteTrapMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = _make_settings(self.tmp)
        self.svc = AgentMemoryService(self.settings)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_creates_file(self):
        path = self.svc.write_trap_memory(
            prompt="Login to admin panel",
            error_summary="TimeoutException: login form not found",
            execution_id="exec-100",
            attempt_count=3,
        )
        self.assertTrue(path.exists())
        self.assertTrue(path.name.startswith("trap_"))
        content = path.read_text(encoding="utf-8")
        self.assertIn("Known Trap", content)
        self.assertIn("Login to admin panel", content)
        self.assertIn("exec-100", content)
        self.assertIn("3 次尝试", content)
        self.assertIn("card_type: `trap`", content)

    def test_error_summary_truncated(self):
        long_error = "E" * 2000
        path = self.svc.write_trap_memory(
            prompt="test", error_summary=long_error,
            execution_id="exec-101", attempt_count=5,
        )
        content = path.read_text(encoding="utf-8")
        # The 反复失败摘要 section uses error_summary[:1000]
        sections = content.split("## 反复失败摘要")
        self.assertEqual(len(sections), 2)
        summary_section = sections[1].split("##")[0]
        # The summary section text (stripped) should be <= 1000 chars
        self.assertLessEqual(len(summary_section.strip()), 1000)

    def test_indexes_into_chromadb(self):
        with patch.object(self.svc, "_index_single_card") as mock_index:
            self.svc.write_trap_memory(
                prompt="test", error_summary="err",
                execution_id="exec-102", attempt_count=2,
            )
            mock_index.assert_called_once()
            args = mock_index.call_args
            self.assertEqual(args[0][2], "trap")


# ---------------------------------------------------------------------------
# rebuild_memory_index
# ---------------------------------------------------------------------------


class RebuildMemoryIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = _make_settings(self.tmp)
        self.svc = AgentMemoryService(self.settings)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_directory_returns_zero(self):
        result = self.svc.rebuild_memory_index()
        self.assertEqual(result["indexed"], 0)
        self.assertEqual(result["collection"], MEMORY_COLLECTION_NAME)

    def test_empty_directory_returns_zero(self):
        self.settings.agent_memory_dir.mkdir(parents=True, exist_ok=True)
        result = self.svc.rebuild_memory_index()
        self.assertEqual(result["indexed"], 0)

    def test_indexes_md_files(self):
        mem_dir = self.settings.agent_memory_dir
        _write_card(mem_dir, "exec-001.md", "# Agent Memory: test\n## 失败类型\nselector_not_found")
        _write_card(mem_dir, "success_exec-002.md", "# Success Pattern: search Baidu")
        _write_card(mem_dir, "trap_exec-003.md", "# Known Trap: login fails")

        result = self.svc.rebuild_memory_index()
        self.assertEqual(result["indexed"], 3)

    def test_skips_empty_files(self):
        mem_dir = self.settings.agent_memory_dir
        _write_card(mem_dir, "exec-001.md", "# Some content")
        _write_card(mem_dir, "empty.md", "")
        result = self.svc.rebuild_memory_index()
        self.assertEqual(result["indexed"], 1)

    def test_no_chromadb_gracefully_degrades(self):
        mem_dir = self.settings.agent_memory_dir
        _write_card(mem_dir, "exec-001.md", "# Content")

        with patch("app.services.agent_memory_service.chromadb", None):
            svc = AgentMemoryService(self.settings)
            result = svc.rebuild_memory_index()
            # Still counts documents, but collection is None
            self.assertEqual(result["indexed"], 1)


# ---------------------------------------------------------------------------
# search_similar
# ---------------------------------------------------------------------------


class SearchSimilarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = _make_settings(self.tmp)
        self.svc = AgentMemoryService(self.settings)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_empty_collection_returns_empty(self):
        result = self.svc.search_similar("timeout error")
        self.assertEqual(result.result_count, 0)
        self.assertEqual(result.cards, [])
        self.assertEqual(result.context, "")

    def test_search_after_indexing(self):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 2
        mock_collection.query.return_value = {
            "documents": [["# Agent Memory: Baidu search timeout"]],
            "metadatas": [[{"source": "exec-001.md", "card_type": "heal"}]],
            "distances": [[0.2]],
        }
        with patch.object(self.svc, "_get_memory_collection", return_value=mock_collection):
            result = self.svc.search_similar("search timeout on Baidu", n_results=2)
        self.assertGreater(result.result_count, 0)
        self.assertGreater(len(result.cards), 0)
        self.assertTrue(result.context)

    def test_search_with_card_type_filter(self):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "documents": [["# Success Pattern: success card"]],
            "metadatas": [[{"source": "success_exec-002.md", "card_type": "success"}]],
            "distances": [[0.15]],
        }
        with patch.object(self.svc, "_get_memory_collection", return_value=mock_collection):
            result = self.svc.search_similar("test", card_type="success")
        for card in result.cards:
            self.assertEqual(card["card_type"], "success")
        # Verify where filter was passed
        call_kwargs = mock_collection.query.call_args
        self.assertEqual(call_kwargs[1]["where"], {"card_type": "success"})

    def test_search_auto_rebuilds_empty_collection(self):
        # First call: count=0, triggers rebuild; second call after rebuild: count=1
        mock_collection = MagicMock()
        call_count = {"n": 0}
        def count_side_effect():
            call_count["n"] += 1
            return 0 if call_count["n"] <= 2 else 1
        mock_collection.count.side_effect = count_side_effect
        mock_collection.query.return_value = {
            "documents": [["# Agent Memory: auto rebuild test"]],
            "metadatas": [[{"source": "exec-001.md", "card_type": "heal"}]],
            "distances": [[0.1]],
        }
        mem_dir = self.settings.agent_memory_dir
        _write_card(mem_dir, "exec-001.md", "# Agent Memory: auto rebuild test")
        with patch.object(self.svc, "_get_memory_collection", return_value=mock_collection):
            result = self.svc.search_similar("auto rebuild")
        # rebuild_memory_index should have been triggered (upsert called)
        mock_collection.upsert.assert_called()

    def test_cards_contain_distance(self):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "documents": [["# Agent Memory: distance check"]],
            "metadatas": [[{"source": "exec-001.md", "card_type": "heal"}]],
            "distances": [[0.42]],
        }
        with patch.object(self.svc, "_get_memory_collection", return_value=mock_collection):
            result = self.svc.search_similar("distance check")
        self.assertEqual(result.result_count, 1)
        self.assertIn("distance", result.cards[0])
        self.assertAlmostEqual(result.cards[0]["distance"], 0.42)

    def test_context_joins_card_content(self):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 2
        mock_collection.query.return_value = {
            "documents": [["# Card One Content", "# Card Two Content"]],
            "metadatas": [[{"source": "a.md", "card_type": "heal"}, {"source": "b.md", "card_type": "heal"}]],
            "distances": [[0.1, 0.2]],
        }
        with patch.object(self.svc, "_get_memory_collection", return_value=mock_collection):
            result = self.svc.search_similar("card", n_results=2)
        self.assertEqual(result.result_count, 2)
        self.assertIn("---", result.context)
        self.assertIn("Card One", result.context)
        self.assertIn("Card Two", result.context)

    def test_search_handles_exception_gracefully(self):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 5
        mock_collection.query.side_effect = RuntimeError("query failed")
        with patch.object(self.svc, "_get_memory_collection", return_value=mock_collection):
            result = self.svc.search_similar("test query")
            self.assertEqual(result.result_count, 0)


# ---------------------------------------------------------------------------
# _index_single_card
# ---------------------------------------------------------------------------


class IndexSingleCardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = _make_settings(self.tmp)
        self.svc = AgentMemoryService(self.settings)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_indexes_card(self):
        mock_collection = MagicMock()
        with patch.object(self.svc, "_get_memory_collection", return_value=mock_collection):
            p = Path(self.tmp / "test_card.md")
            self.svc._index_single_card(p, "# Content", "success")
            mock_collection.upsert.assert_called_once()
            call_kwargs = mock_collection.upsert.call_args
            self.assertEqual(call_kwargs[1]["ids"], ["mem_test_card"])
            self.assertEqual(call_kwargs[1]["metadatas"][0]["card_type"], "success")

    def test_no_chromadb_no_error(self):
        with patch.object(self.svc, "_get_memory_collection", return_value=None):
            # Should not raise
            self.svc._index_single_card(Path("x.md"), "content", "heal")

    def test_upsert_failure_logged_not_raised(self):
        mock_collection = MagicMock()
        mock_collection.upsert.side_effect = RuntimeError("db error")
        with patch.object(self.svc, "_get_memory_collection", return_value=mock_collection):
            # Should not raise
            self.svc._index_single_card(Path("x.md"), "content", "trap")


# ---------------------------------------------------------------------------
# SearchMemoryTool
# ---------------------------------------------------------------------------


class SearchMemoryToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = _make_settings(self.tmp)
        self.memory_svc = AgentMemoryService(self.settings)
        self.tool = SearchMemoryTool(self.memory_svc)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tool_properties(self):
        self.assertEqual(self.tool.name, "search_memory")
        self.assertIn("long-term memory", self.tool.description)
        schema = self.tool.parameters_schema
        self.assertIn("query", schema["properties"])
        self.assertEqual(schema["required"], ["query"])

    def test_empty_query_fails(self):
        result = self.tool.execute(query="")
        self.assertFalse(result.success)
        self.assertIn("empty", result.error.lower())

    def test_whitespace_only_query_fails(self):
        result = self.tool.execute(query="   ")
        self.assertFalse(result.success)

    def test_no_results(self):
        result = self.tool.execute(query="some random query")
        self.assertTrue(result.success)
        self.assertEqual(result.data["result_count"], 0)
        self.assertIn("No similar", result.summary)

    def test_returns_results(self):
        mock_result = MemorySearchResult(
            cards=[
                {"content": "# Agent Memory: timeout on Baidu", "source": "exec-001.md",
                 "card_type": "heal", "distance": 0.3}
            ],
            context="# Agent Memory: timeout on Baidu",
            result_count=1,
        )
        with patch.object(self.memory_svc, "search_similar", return_value=mock_result):
            result = self.tool.execute(query="timeout error on Baidu search")
        self.assertTrue(result.success)
        self.assertGreater(result.data["result_count"], 0)
        self.assertIn("Found", result.summary)
        card = result.data["cards"][0]
        self.assertIn("source", card)
        self.assertIn("card_type", card)
        self.assertIn("content_preview", card)
        self.assertIn("distance", card)
        self.assertTrue(result.data["context"])

    def test_with_card_type_filter(self):
        mock_result = MemorySearchResult(
            cards=[{"content": "# Success Pattern: ok", "source": "s.md",
                    "card_type": "success", "distance": 0.1}],
            context="# Success Pattern: ok",
            result_count=1,
        )
        with patch.object(self.memory_svc, "search_similar", return_value=mock_result):
            result = self.tool.execute(query="test", card_type="success")
        self.assertTrue(result.success)
        for card in result.data["cards"]:
            self.assertEqual(card["card_type"], "success")

    def test_n_results_parameter(self):
        mock_result = MemorySearchResult(
            cards=[
                {"content": "card 0", "source": "a.md", "card_type": "heal", "distance": 0.1},
                {"content": "card 1", "source": "b.md", "card_type": "heal", "distance": 0.2},
            ],
            context="card 0\n\n---\n\ncard 1",
            result_count=2,
        )
        with patch.object(self.memory_svc, "search_similar", return_value=mock_result) as mock_search:
            result = self.tool.execute(query="card", n_results=2)
        self.assertTrue(result.success)
        self.assertLessEqual(result.data["result_count"], 2)
        # Verify n_results was passed through
        mock_search.assert_called_once_with(query="card", n_results=2, card_type=None)

    def test_content_preview_truncated(self):
        long_content = "# Agent Memory: long\n" + "A" * 2000
        mock_result = MemorySearchResult(
            cards=[{"content": long_content, "source": "exec-long.md",
                    "card_type": "heal", "distance": 0.1}],
            context=long_content[:2000],
            result_count=1,
        )
        with patch.object(self.memory_svc, "search_similar", return_value=mock_result):
            result = self.tool.execute(query="long")
        self.assertTrue(result.success)
        self.assertEqual(result.data["result_count"], 1)
        preview = result.data["cards"][0]["content_preview"]
        self.assertLessEqual(len(preview), 500)

    def test_to_function_schema(self):
        schema = self.tool.to_function_schema()
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "search_memory")
        self.assertIn("properties", schema["function"]["parameters"])

    def test_exception_returns_error(self):
        mock_memory = MagicMock()
        mock_memory.search_similar.side_effect = RuntimeError("boom")
        tool = SearchMemoryTool(mock_memory)
        result = tool.execute(query="test")
        self.assertFalse(result.success)
        self.assertIn("boom", result.error)


if __name__ == "__main__":
    unittest.main()
