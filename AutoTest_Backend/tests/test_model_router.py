"""Tests for ModelRouter: task-type + complexity → ModelConfig routing."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from . import _bootstrap  # noqa: F401 — path bootstrap

from app.core.config import Settings
from app.services.model_router import (
    AGENT_REASONING,
    ALL_COMPLEXITIES,
    ALL_TASK_TYPES,
    CODE_GENERATION,
    COMPLEX_FLOW,
    DIAGNOSIS,
    EMBEDDING,
    ModelConfig,
    ModelRouter,
    MULTI_STEP,
    PLANNING,
    REPAIR,
    SIMPLE,
    TASK_ANALYSIS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides) -> Settings:
    """Create a Settings instance with sensible test defaults."""
    defaults = {
        "DEEPSEEK_API_KEY": "test-key",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "MODEL_NAME": "deepseek-chat",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ===========================================================================
# 1. ModelConfig dataclass tests
# ===========================================================================


class TestModelConfig(unittest.TestCase):
    """Tests for the ModelConfig frozen dataclass."""

    def test_defaults(self):
        cfg = ModelConfig(model_name="m1")
        self.assertEqual(cfg.model_name, "m1")
        self.assertEqual(cfg.temperature, 0.1)
        self.assertIsNone(cfg.max_tokens)
        self.assertIsNone(cfg.base_url)
        self.assertEqual(cfg.extra, {})

    def test_custom_values(self):
        cfg = ModelConfig(
            model_name="gpt-4",
            temperature=0.7,
            max_tokens=4096,
            base_url="https://custom.api",
            extra={"top_p": 0.9},
        )
        self.assertEqual(cfg.model_name, "gpt-4")
        self.assertEqual(cfg.temperature, 0.7)
        self.assertEqual(cfg.max_tokens, 4096)
        self.assertEqual(cfg.base_url, "https://custom.api")
        self.assertEqual(cfg.extra, {"top_p": 0.9})

    def test_frozen(self):
        cfg = ModelConfig(model_name="m1")
        with self.assertRaises(AttributeError):
            cfg.model_name = "m2"  # type: ignore[misc]

    def test_to_dict_minimal(self):
        cfg = ModelConfig(model_name="m1")
        d = cfg.to_dict()
        self.assertEqual(d, {"model_name": "m1", "temperature": 0.1})

    def test_to_dict_full(self):
        cfg = ModelConfig(
            model_name="m1",
            temperature=0.5,
            max_tokens=2048,
            base_url="https://x",
            extra={"k": "v"},
        )
        d = cfg.to_dict()
        self.assertEqual(d["model_name"], "m1")
        self.assertEqual(d["temperature"], 0.5)
        self.assertEqual(d["max_tokens"], 2048)
        self.assertEqual(d["base_url"], "https://x")
        self.assertEqual(d["extra"], {"k": "v"})

    def test_equality(self):
        a = ModelConfig(model_name="m1", temperature=0.1)
        b = ModelConfig(model_name="m1", temperature=0.1)
        self.assertEqual(a, b)

    def test_inequality(self):
        a = ModelConfig(model_name="m1")
        b = ModelConfig(model_name="m2")
        self.assertNotEqual(a, b)


# ===========================================================================
# 2. ModelRouter default routing tests
# ===========================================================================


class TestModelRouterDefaults(unittest.TestCase):
    """Default routing: all tasks should use Settings.MODEL_NAME."""

    def setUp(self):
        self.settings = _make_settings()
        self.router = ModelRouter(self.settings)

    def test_default_model_property(self):
        self.assertEqual(self.router.default_model, "deepseek-chat")

    def test_all_task_types_return_default_model(self):
        for tt in ALL_TASK_TYPES:
            if tt == EMBEDDING:
                continue  # embedding has no default routing rule
            cfg = self.router.select_model(tt, SIMPLE)
            self.assertEqual(cfg.model_name, "deepseek-chat", f"task_type={tt}")

    def test_all_complexities_return_config(self):
        for c in ALL_COMPLEXITIES:
            cfg = self.router.select_model(CODE_GENERATION, c)
            self.assertIsInstance(cfg, ModelConfig)
            self.assertEqual(cfg.model_name, "deepseek-chat")

    def test_unknown_task_type_falls_back(self):
        cfg = self.router.select_model("unknown_type", SIMPLE)
        self.assertEqual(cfg.model_name, "deepseek-chat")
        self.assertEqual(cfg.temperature, 0.1)

    def test_task_analysis_temperature(self):
        cfg = self.router.select_model(TASK_ANALYSIS, SIMPLE)
        self.assertEqual(cfg.temperature, 0.1)

    def test_planning_temperature(self):
        cfg = self.router.select_model(PLANNING, MULTI_STEP)
        self.assertEqual(cfg.temperature, 0.1)

    def test_code_generation_simple_temperature(self):
        cfg = self.router.select_model(CODE_GENERATION, SIMPLE)
        self.assertEqual(cfg.temperature, 0.1)

    def test_code_generation_complex_temperature(self):
        cfg = self.router.select_model(CODE_GENERATION, COMPLEX_FLOW)
        self.assertEqual(cfg.temperature, 0.15)

    def test_repair_default_temperature(self):
        cfg = self.router.select_model(REPAIR, SIMPLE)
        self.assertEqual(cfg.temperature, 0.1)

    def test_repair_complex_temperature(self):
        cfg = self.router.select_model(REPAIR, COMPLEX_FLOW)
        self.assertEqual(cfg.temperature, 0.15)

    def test_diagnosis_temperature(self):
        cfg = self.router.select_model(DIAGNOSIS, SIMPLE)
        self.assertEqual(cfg.temperature, 0.1)

    def test_agent_reasoning_simple_temperature(self):
        cfg = self.router.select_model(AGENT_REASONING, SIMPLE)
        self.assertEqual(cfg.temperature, 0.1)

    def test_agent_reasoning_complex_temperature(self):
        cfg = self.router.select_model(AGENT_REASONING, COMPLEX_FLOW)
        self.assertEqual(cfg.temperature, 0.15)

    def test_max_tokens_none_by_default(self):
        for tt in [TASK_ANALYSIS, PLANNING, CODE_GENERATION, REPAIR, DIAGNOSIS]:
            cfg = self.router.select_model(tt, SIMPLE)
            self.assertIsNone(cfg.max_tokens, f"task_type={tt}")

    def test_base_url_none_by_default(self):
        cfg = self.router.select_model(CODE_GENERATION, SIMPLE)
        self.assertIsNone(cfg.base_url)


# ===========================================================================
# 3. Programmatic override tests
# ===========================================================================


class TestModelRouterOverrides(unittest.TestCase):
    """Tests for add_override / remove_override."""

    def setUp(self):
        self.settings = _make_settings()
        self.router = ModelRouter(self.settings)

    def test_add_override_general(self):
        self.router.add_override(CODE_GENERATION, "deepseek-coder")
        cfg = self.router.select_model(CODE_GENERATION, SIMPLE)
        self.assertEqual(cfg.model_name, "deepseek-coder")

    def test_add_override_specific_complexity(self):
        self.router.add_override(CODE_GENERATION, "gpt-4", complexity=COMPLEX_FLOW)
        # Complex should use override
        cfg_complex = self.router.select_model(CODE_GENERATION, COMPLEX_FLOW)
        self.assertEqual(cfg_complex.model_name, "gpt-4")
        # Simple should still use default
        cfg_simple = self.router.select_model(CODE_GENERATION, SIMPLE)
        self.assertEqual(cfg_simple.model_name, "deepseek-chat")

    def test_specific_override_takes_precedence(self):
        self.router.add_override(CODE_GENERATION, "general-model")
        self.router.add_override(CODE_GENERATION, "specific-model", complexity=COMPLEX_FLOW)
        cfg = self.router.select_model(CODE_GENERATION, COMPLEX_FLOW)
        self.assertEqual(cfg.model_name, "specific-model")

    def test_general_override_used_when_no_specific(self):
        self.router.add_override(CODE_GENERATION, "general-model")
        cfg = self.router.select_model(CODE_GENERATION, MULTI_STEP)
        self.assertEqual(cfg.model_name, "general-model")

    def test_remove_override(self):
        self.router.add_override(CODE_GENERATION, "deepseek-coder")
        self.router.remove_override(CODE_GENERATION)
        cfg = self.router.select_model(CODE_GENERATION, SIMPLE)
        self.assertEqual(cfg.model_name, "deepseek-chat")

    def test_remove_specific_override(self):
        self.router.add_override(CODE_GENERATION, "gpt-4", complexity=COMPLEX_FLOW)
        self.router.remove_override(CODE_GENERATION, complexity=COMPLEX_FLOW)
        cfg = self.router.select_model(CODE_GENERATION, COMPLEX_FLOW)
        self.assertEqual(cfg.model_name, "deepseek-chat")

    def test_remove_nonexistent_override_no_error(self):
        self.router.remove_override(CODE_GENERATION)  # should not raise

    def test_list_overrides_empty(self):
        self.assertEqual(self.router.list_overrides(), {})

    def test_list_overrides_populated(self):
        self.router.add_override(CODE_GENERATION, "coder")
        self.router.add_override(REPAIR, "repair-model", complexity=COMPLEX_FLOW)
        overrides = self.router.list_overrides()
        self.assertEqual(overrides[(CODE_GENERATION, None)], "coder")
        self.assertEqual(overrides[(REPAIR, COMPLEX_FLOW)], "repair-model")

    def test_override_does_not_affect_other_task_types(self):
        self.router.add_override(CODE_GENERATION, "coder")
        cfg = self.router.select_model(DIAGNOSIS, SIMPLE)
        self.assertEqual(cfg.model_name, "deepseek-chat")

    def test_override_preserves_temperature_from_rules(self):
        self.router.add_override(CODE_GENERATION, "coder")
        cfg = self.router.select_model(CODE_GENERATION, COMPLEX_FLOW)
        self.assertEqual(cfg.model_name, "coder")
        self.assertEqual(cfg.temperature, 0.15)  # from default rule


# ===========================================================================
# 4. Env-var override tests
# ===========================================================================


class TestModelRouterEnvOverrides(unittest.TestCase):
    """Tests for environment-variable-based model overrides."""

    def test_env_override_code_generation(self):
        settings = _make_settings(MODEL_CODE_GENERATION="deepseek-coder")
        router = ModelRouter(settings)
        cfg = router.select_model(CODE_GENERATION, SIMPLE)
        self.assertEqual(cfg.model_name, "deepseek-coder")

    def test_env_override_task_analysis(self):
        settings = _make_settings(MODEL_TASK_ANALYSIS="gpt-4o-mini")
        router = ModelRouter(settings)
        cfg = router.select_model(TASK_ANALYSIS, SIMPLE)
        self.assertEqual(cfg.model_name, "gpt-4o-mini")

    def test_env_override_planning(self):
        settings = _make_settings(MODEL_PLANNING="planner-model")
        router = ModelRouter(settings)
        cfg = router.select_model(PLANNING, MULTI_STEP)
        self.assertEqual(cfg.model_name, "planner-model")

    def test_env_override_repair(self):
        settings = _make_settings(MODEL_REPAIR="repair-model")
        router = ModelRouter(settings)
        cfg = router.select_model(REPAIR, SIMPLE)
        self.assertEqual(cfg.model_name, "repair-model")

    def test_env_override_diagnosis(self):
        settings = _make_settings(MODEL_DIAGNOSIS="diag-model")
        router = ModelRouter(settings)
        cfg = router.select_model(DIAGNOSIS, COMPLEX_FLOW)
        self.assertEqual(cfg.model_name, "diag-model")

    def test_env_override_agent_reasoning(self):
        settings = _make_settings(MODEL_AGENT_REASONING="agent-model")
        router = ModelRouter(settings)
        cfg = router.select_model(AGENT_REASONING, SIMPLE)
        self.assertEqual(cfg.model_name, "agent-model")

    def test_programmatic_override_beats_env(self):
        settings = _make_settings(MODEL_CODE_GENERATION="env-model")
        router = ModelRouter(settings)
        router.add_override(CODE_GENERATION, "programmatic-model")
        cfg = router.select_model(CODE_GENERATION, SIMPLE)
        self.assertEqual(cfg.model_name, "programmatic-model")

    def test_specific_programmatic_override_beats_env(self):
        settings = _make_settings(MODEL_CODE_GENERATION="env-model")
        router = ModelRouter(settings)
        router.add_override(CODE_GENERATION, "specific-model", complexity=COMPLEX_FLOW)
        cfg = router.select_model(CODE_GENERATION, COMPLEX_FLOW)
        self.assertEqual(cfg.model_name, "specific-model")
        # Other complexity still uses env override
        cfg_simple = router.select_model(CODE_GENERATION, SIMPLE)
        self.assertEqual(cfg_simple.model_name, "env-model")

    def test_no_env_override_when_not_set(self):
        settings = _make_settings()
        router = ModelRouter(settings)
        cfg = router.select_model(CODE_GENERATION, SIMPLE)
        self.assertEqual(cfg.model_name, "deepseek-chat")

    def test_empty_env_override_ignored(self):
        settings = _make_settings(MODEL_CODE_GENERATION="")
        router = ModelRouter(settings)
        cfg = router.select_model(CODE_GENERATION, SIMPLE)
        self.assertEqual(cfg.model_name, "deepseek-chat")

    def test_whitespace_env_override_ignored(self):
        settings = _make_settings(MODEL_CODE_GENERATION="   ")
        router = ModelRouter(settings)
        cfg = router.select_model(CODE_GENERATION, SIMPLE)
        self.assertEqual(cfg.model_name, "deepseek-chat")


# ===========================================================================
# 5. LLMService integration tests (model_config parameter)
# ===========================================================================


class TestLLMServiceModelConfig(unittest.TestCase):
    """Tests that LLMService methods accept and use ModelConfig."""

    def _make_llm_service(self):
        from app.services.llm_service import LLMService
        settings = _make_settings()
        return LLMService(settings)

    @patch("app.services.llm_service.OpenAI")
    def test_complete_uses_model_config_model_name(self, mock_openai_cls):
        svc = self._make_llm_service()
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "result"
        mock_client.chat.completions.create.return_value = mock_response

        cfg = ModelConfig(model_name="custom-model", temperature=0.5)
        result = svc._complete(
            messages=[{"role": "user", "content": "hi"}],
            model_config=cfg,
        )
        self.assertEqual(result, "result")
        call_kwargs = mock_client.chat.completions.create.call_args
        self.assertEqual(call_kwargs.kwargs["model"], "custom-model")
        self.assertEqual(call_kwargs.kwargs["temperature"], 0.5)

    @patch("app.services.llm_service.OpenAI")
    def test_complete_uses_max_tokens(self, mock_openai_cls):
        svc = self._make_llm_service()
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "result"
        mock_client.chat.completions.create.return_value = mock_response

        cfg = ModelConfig(model_name="m1", max_tokens=2048)
        svc._complete(
            messages=[{"role": "user", "content": "hi"}],
            model_config=cfg,
        )
        call_kwargs = mock_client.chat.completions.create.call_args
        self.assertEqual(call_kwargs.kwargs["max_tokens"], 2048)

    @patch("app.services.llm_service.OpenAI")
    def test_complete_no_max_tokens_when_none(self, mock_openai_cls):
        svc = self._make_llm_service()
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "result"
        mock_client.chat.completions.create.return_value = mock_response

        cfg = ModelConfig(model_name="m1")
        svc._complete(
            messages=[{"role": "user", "content": "hi"}],
            model_config=cfg,
        )
        call_kwargs = mock_client.chat.completions.create.call_args
        self.assertNotIn("max_tokens", call_kwargs.kwargs)

    @patch("app.services.llm_service.OpenAI")
    def test_complete_without_model_config_uses_defaults(self, mock_openai_cls):
        svc = self._make_llm_service()
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "result"
        mock_client.chat.completions.create.return_value = mock_response

        svc._complete(messages=[{"role": "user", "content": "hi"}])
        call_kwargs = mock_client.chat.completions.create.call_args
        self.assertEqual(call_kwargs.kwargs["model"], "deepseek-chat")
        self.assertEqual(call_kwargs.kwargs["temperature"], 0.1)

    @patch("app.services.llm_service.OpenAI")
    def test_custom_base_url_creates_new_client(self, mock_openai_cls):
        svc = self._make_llm_service()
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "result"
        mock_client.chat.completions.create.return_value = mock_response

        cfg = ModelConfig(model_name="m1", base_url="https://custom.api")
        svc._complete(
            messages=[{"role": "user", "content": "hi"}],
            model_config=cfg,
        )
        # Should have created a client with custom base_url
        mock_openai_cls.assert_called_with(
            api_key="test-key",
            base_url="https://custom.api",
        )

    @patch("app.services.llm_service.OpenAI")
    def test_agent_chat_passes_model_config(self, mock_openai_cls):
        svc = self._make_llm_service()
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "result"
        mock_client.chat.completions.create.return_value = mock_response

        cfg = ModelConfig(model_name="agent-model", temperature=0.3)
        svc.agent_chat(
            system_prompt="sys",
            user_message="msg",
            model_config=cfg,
        )
        call_kwargs = mock_client.chat.completions.create.call_args
        self.assertEqual(call_kwargs.kwargs["model"], "agent-model")
        self.assertEqual(call_kwargs.kwargs["temperature"], 0.3)

    @patch("app.services.llm_service.OpenAI")
    def test_chat_passes_model_config(self, mock_openai_cls):
        svc = self._make_llm_service()
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "code"
        mock_client.chat.completions.create.return_value = mock_response

        cfg = ModelConfig(model_name="code-model")
        svc.chat("generate a test", model_config=cfg)
        call_kwargs = mock_client.chat.completions.create.call_args
        self.assertEqual(call_kwargs.kwargs["model"], "code-model")


# ===========================================================================
# 6. Constants & edge cases
# ===========================================================================


class TestConstants(unittest.TestCase):
    """Verify constant values are consistent."""

    def test_all_task_types_has_expected_members(self):
        expected = {
            "task_analysis", "planning", "code_generation",
            "repair", "diagnosis", "agent_reasoning", "embedding",
        }
        self.assertEqual(ALL_TASK_TYPES, expected)

    def test_all_complexities_has_expected_members(self):
        expected = {"simple", "multi_step", "complex_flow"}
        self.assertEqual(ALL_COMPLEXITIES, expected)

    def test_task_type_constants_match(self):
        self.assertEqual(TASK_ANALYSIS, "task_analysis")
        self.assertEqual(PLANNING, "planning")
        self.assertEqual(CODE_GENERATION, "code_generation")
        self.assertEqual(REPAIR, "repair")
        self.assertEqual(DIAGNOSIS, "diagnosis")
        self.assertEqual(AGENT_REASONING, "agent_reasoning")
        self.assertEqual(EMBEDDING, "embedding")

    def test_complexity_constants_match(self):
        self.assertEqual(SIMPLE, "simple")
        self.assertEqual(MULTI_STEP, "multi_step")
        self.assertEqual(COMPLEX_FLOW, "complex_flow")


class TestEdgeCases(unittest.TestCase):
    """Edge cases for ModelRouter."""

    def setUp(self):
        self.settings = _make_settings()
        self.router = ModelRouter(self.settings)

    def test_embedding_task_type_returns_default(self):
        cfg = self.router.select_model(EMBEDDING, SIMPLE)
        self.assertEqual(cfg.model_name, "deepseek-chat")
        self.assertEqual(cfg.temperature, 0.1)

    def test_empty_string_task_type(self):
        cfg = self.router.select_model("", SIMPLE)
        self.assertEqual(cfg.model_name, "deepseek-chat")

    def test_empty_string_complexity(self):
        cfg = self.router.select_model(CODE_GENERATION, "")
        self.assertIsInstance(cfg, ModelConfig)

    def test_custom_model_name_in_settings(self):
        settings = _make_settings(MODEL_NAME="custom-default")
        router = ModelRouter(settings)
        cfg = router.select_model(TASK_ANALYSIS, SIMPLE)
        self.assertEqual(cfg.model_name, "custom-default")

    def test_multiple_env_overrides(self):
        settings = _make_settings(
            MODEL_CODE_GENERATION="coder",
            MODEL_DIAGNOSIS="diag",
            MODEL_REPAIR="repair-m",
        )
        router = ModelRouter(settings)
        self.assertEqual(router.select_model(CODE_GENERATION, SIMPLE).model_name, "coder")
        self.assertEqual(router.select_model(DIAGNOSIS, SIMPLE).model_name, "diag")
        self.assertEqual(router.select_model(REPAIR, SIMPLE).model_name, "repair-m")
        # Non-overridden task types still use default
        self.assertEqual(router.select_model(PLANNING, SIMPLE).model_name, "deepseek-chat")

    def test_router_is_reusable_across_calls(self):
        cfg1 = self.router.select_model(CODE_GENERATION, SIMPLE)
        cfg2 = self.router.select_model(CODE_GENERATION, SIMPLE)
        self.assertEqual(cfg1, cfg2)

    def test_override_then_different_complexity(self):
        self.router.add_override(REPAIR, "repair-v2")
        cfg_s = self.router.select_model(REPAIR, SIMPLE)
        cfg_c = self.router.select_model(REPAIR, COMPLEX_FLOW)
        # Both use overridden model name
        self.assertEqual(cfg_s.model_name, "repair-v2")
        self.assertEqual(cfg_c.model_name, "repair-v2")
        # But temperatures may differ per complexity
        self.assertEqual(cfg_s.temperature, 0.1)
        self.assertEqual(cfg_c.temperature, 0.15)


if __name__ == "__main__":
    unittest.main()
