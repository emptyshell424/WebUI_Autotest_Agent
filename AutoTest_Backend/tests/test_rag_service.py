import unittest

from . import _bootstrap
from .runtime_support import RuntimeWorkspaceTestCase

from app.core.config import Settings
from app.services.rag_service import RAGService


class RAGServiceTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        self.temp_dir = self.create_temp_dir("rag-service")
        knowledge_dir = self.temp_dir / "docs" / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)

        (knowledge_dir / "login_flows.md").write_text(
            """
Keywords: login, 登录, username, password, dashboard, admin.

Wait for the username and password inputs, then assert the dashboard text name: admin after login.

登录后应断言 dashboard 或 `name: admin`，而不是只断言点击成功。
            """.strip(),
            encoding="utf-8",
        )
        (knowledge_dir / "vue_admin_template_patterns.md").write_text(
            """
Keywords: vue-admin-template, Dashboard, Table, Form, Create.

The dashboard page shows name: admin. The Form page contains Activity name and a Create button.

Form 页面包含 Activity name 和 Create 按钮。
            """.strip(),
            encoding="utf-8",
        )
        (knowledge_dir / "safe_code_generation_rules.md").write_text(
            """
Keywords: safe import, sys, os, subprocess, urllib, quote_plus.

Do not import sys, os, subprocess, or pathlib in ordinary Selenium UI tests. If a search-results URL must be built safely during repair, urllib.parse.quote_plus is allowed.

普通 UI 测试不要导入 sys、os、subprocess、pathlib；如果修复阶段需要安全构造结果页 URL，则允许使用 urllib.parse.quote_plus。
            """.strip(),
            encoding="utf-8",
        )
        (knowledge_dir / "bilingual_ui_prompt_patterns.md").write_text(
            """
Keywords: 中文 prompt, 登录, 搜索, 点击, 验证.

对于中文 prompt，应把“验证进入首页”映射为稳定页面锚点断言。
            """.strip(),
            encoding="utf-8",
        )
        (knowledge_dir / "search_flows.md").write_text(
            """
Keywords: search, 搜索, 百度, kw, input[name='wd'], TimeoutException, #content_left, Test Completed.

Baidu search defaults to interaction-first. The first generated script should preserve homepage interaction.

If the homepage search anchors such as kw or input[name='wd'] time out during self-heal, the repair flow may downgrade to the direct results page.
            """.strip(),
            encoding="utf-8",
        )

        self.settings = Settings(
            DEEPSEEK_API_KEY=None,
            SQLITE_DB_PATH=str(self.temp_dir / "data" / "app.db"),
            VECTOR_STORE_DIR=str(self.temp_dir / "data" / "rag"),
            KNOWLEDGE_BASE_DIR=str(knowledge_dir),
            EXECUTIONS_DIR=str(self.temp_dir / "runs"),
        )
        self.rag = RAGService(self.settings)
        self.rag.rebuild_index()

    def test_chinese_login_prompt_matches_login_docs(self) -> None:
        result = self.rag.search(
            "打开登录页面，输入用户名 admin 和密码 111111，并验证进入 Dashboard 页面。"
        )
        self.assertGreaterEqual(result.result_count, 1)
        self.assertIn("login_flows.md", result.sources)
        self.assertIn("name: admin", result.context)
        self.assertEqual(result.retrieval_mode, "hybrid_rerank")

    def test_form_prompt_matches_vue_admin_template_patterns(self) -> None:
        result = self.rag.search("进入 Form 页面，填写 Activity name，然后点击 Create 按钮。")
        self.assertGreaterEqual(result.result_count, 1)
        self.assertIn("vue_admin_template_patterns.md", result.sources)
        self.assertTrue("Create" in result.context or "按钮" in result.context)

    def test_safe_generation_prompt_matches_safe_rules(self) -> None:
        result = self.rag.search("生成安全的测试脚本，可以使用 quote_plus，但不要导入 sys 或 os。")
        self.assertIn("safe_code_generation_rules.md", result.sources)
        self.assertIn("quote_plus", result.context)

    def test_chinese_prompt_matches_bilingual_patterns(self) -> None:
        result = self.rag.search("点击登录按钮后，验证进入首页。")
        self.assertIn("bilingual_ui_prompt_patterns.md", result.sources)
        self.assertGreaterEqual(result.result_count, 1)

    def test_baidu_search_prompt_matches_search_patterns(self) -> None:
        result = self.rag.search("打开百度，搜索 DeepSeek，等待结果页面出现，然后打印测试完成。")
        self.assertIn("search_flows.md", result.sources)
        self.assertGreaterEqual(result.result_count, 1)

    def test_homepage_search_timeout_prompt_matches_search_patterns(self) -> None:
        result = self.rag.search("百度首页搜索框 kw 超时，TimeoutException，找不到输入框。")
        self.assertIn("search_flows.md", result.sources)
        self.assertGreaterEqual(result.result_count, 1)

    def test_explicit_modes_return_mode_flag(self) -> None:
        vector_result = self.rag.search(
            "进入 Form 页面，填写 Activity name，然后点击 Create 按钮。",
            retrieval_mode="vector",
        )
        hybrid_result = self.rag.search(
            "进入 Form 页面，填写 Activity name，然后点击 Create 按钮。",
            retrieval_mode="hybrid",
        )
        rerank_result = self.rag.search(
            "进入 Form 页面，填写 Activity name，然后点击 Create 按钮。",
            retrieval_mode="hybrid_rerank",
        )

        self.assertEqual(vector_result.retrieval_mode, "vector")
        self.assertEqual(hybrid_result.retrieval_mode, "hybrid")
        self.assertEqual(rerank_result.retrieval_mode, "hybrid_rerank")
        self.assertGreaterEqual(hybrid_result.result_count, 1)
        self.assertGreaterEqual(rerank_result.result_count, 1)


if __name__ == "__main__":
    unittest.main()
