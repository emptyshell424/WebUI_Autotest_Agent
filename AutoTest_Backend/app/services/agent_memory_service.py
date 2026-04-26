from __future__ import annotations

import re
from pathlib import Path

from app.core.config import Settings
from app.models import ExecutionRecord, SelfHealAttemptRecord, TestCaseRecord


class AgentMemoryService:
    """Persist successful self-heal lessons as Markdown knowledge documents."""

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
        return self._dedupe(tokens)[:30]

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
