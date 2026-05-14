"""ModelRouter: route LLM calls to different model configurations.

Based on task type, complexity, env-var overrides, and programmatic
overrides, selects the appropriate ModelConfig (model name, temperature).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings

logger = logging.getLogger("autotest.model_router")

TASK_ANALYSIS = "task_analysis"
PLANNING = "planning"
CODE_GENERATION = "code_generation"
REPAIR = "repair"
DIAGNOSIS = "diagnosis"
AGENT_REASONING = "agent_reasoning"
EMBEDDING = "embedding"

ALL_TASK_TYPES = frozenset({
    TASK_ANALYSIS, PLANNING, CODE_GENERATION,
    REPAIR, DIAGNOSIS, AGENT_REASONING, EMBEDDING,
})

SIMPLE = "simple"
MULTI_STEP = "multi_step"
COMPLEX_FLOW = "complex_flow"

ALL_COMPLEXITIES = frozenset({SIMPLE, MULTI_STEP, COMPLEX_FLOW})


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Immutable configuration for a single LLM call."""

    model_name: str
    temperature: float = 0.1
    max_tokens: int | None = None
    base_url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "model_name": self.model_name,
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            d["max_tokens"] = self.max_tokens
        if self.base_url is not None:
            d["base_url"] = self.base_url
        if self.extra:
            d["extra"] = self.extra
        return d


class ModelRouter:
    """Select model configuration based on task type and complexity.

    Resolution order (first match wins):
    1. Programmatic override for (task_type, complexity)
    2. Programmatic override for (task_type, None)
    3. Env-var override (e.g. MODEL_CODE_GENERATION)
    4. Settings.MODEL_NAME
    """

    _ENV_SUFFIX_MAP: dict[str, str] = {
        TASK_ANALYSIS: "TASK_ANALYSIS",
        PLANNING: "PLANNING",
        CODE_GENERATION: "CODE_GENERATION",
        REPAIR: "REPAIR",
        DIAGNOSIS: "DIAGNOSIS",
        AGENT_REASONING: "AGENT_REASONING",
    }

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._overrides: dict[tuple[str, str | None], str] = {}
        self._load_env_overrides()

    @property
    def default_model(self) -> str:
        return self._settings.MODEL_NAME

    def select_model(self, task_type: str, complexity: str = SIMPLE) -> ModelConfig:
        model_name = self._resolve_model_name(task_type, complexity)
        temperature = 0.15 if complexity == COMPLEX_FLOW else 0.1
        return ModelConfig(model_name=model_name, temperature=temperature)

    def add_override(self, task_type: str, model_name: str, complexity: str | None = None) -> None:
        self._overrides[(task_type, complexity)] = model_name

    def remove_override(self, task_type: str, complexity: str | None = None) -> None:
        self._overrides.pop((task_type, complexity), None)

    def list_overrides(self) -> dict[tuple[str, str | None], str]:
        return dict(self._overrides)

    def _resolve_model_name(self, task_type: str, complexity: str) -> str:
        if (task_type, complexity) in self._overrides:
            return self._overrides[(task_type, complexity)]
        if (task_type, None) in self._overrides:
            return self._overrides[(task_type, None)]
        env_key = f"_env_{task_type}"
        if (env_key, None) in self._overrides:
            return self._overrides[(env_key, None)]
        return self._settings.MODEL_NAME

    def _load_env_overrides(self) -> None:
        for task_type, suffix in self._ENV_SUFFIX_MAP.items():
            attr = f"MODEL_{suffix}"
            value = getattr(self._settings, attr, None)
            if value and isinstance(value, str) and value.strip():
                env_key = f"_env_{task_type}"
                self._overrides[(env_key, None)] = value.strip()
                logger.info(
                    "ModelRouter: env override %s=%s for task_type=%s",
                    attr, value.strip(), task_type,
                )
