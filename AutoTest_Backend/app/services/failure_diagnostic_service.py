from dataclasses import dataclass


FAILURE_TYPES = {
    "selector_not_found",
    "wait_timeout",
    "assertion_failed",
    "safety_blocked",
    "unknown_failure",
}


@dataclass(frozen=True, slots=True)
class FailureDiagnosis:
    failure_type: str
    failure_signal: str
    suspected_root_cause: str
    repair_hint: str


class FailureDiagnosticService:
    def diagnose(
        self,
        *,
        error: str | None,
        logs: str | None,
        validation_errors: list[str] | None = None,
    ) -> FailureDiagnosis:
        validation_errors = validation_errors or []
        combined = "\n".join(
            part for part in [error or "", logs or "", "\n".join(validation_errors)] if part
        )
        normalized = combined.lower()

        if validation_errors or "blocked by safety validation" in normalized or "is not allowed" in normalized:
            return FailureDiagnosis(
                failure_type="safety_blocked",
                failure_signal=self._signal(combined, "Safety validation blocked execution."),
                suspected_root_cause="Generated or repaired code used imports or calls that violate backend safety rules.",
                repair_hint="Remove unsafe imports, local file operations, process calls, dynamic execution, and unrelated runtime helpers.",
            )

        if self._looks_like_assertion_failure(normalized):
            return FailureDiagnosis(
                failure_type="assertion_failed",
                failure_signal=self._signal(combined, "Assertion failure."),
                suspected_root_cause="The page reached a terminal state, but the observed content or URL did not match the expected assertion.",
                repair_hint="Keep the business intent, wait for the final UI state, then repair the assertion to check stable visible text, URL, or component state.",
            )

        if self._looks_like_wait_timeout(normalized):
            return FailureDiagnosis(
                failure_type="wait_timeout",
                failure_signal=self._signal(combined, "Timeout while waiting for a browser condition."),
                suspected_root_cause="The script waited for a condition that did not become true in time, often because the page was still loading, the condition is too strict, or the selector targets the wrong state.",
                repair_hint="Use explicit waits for page readiness, loading-mask disappearance, visibility, or clickability; avoid fixed sleeps as the primary synchronization mechanism.",
            )

        if self._looks_like_selector_not_found(normalized):
            return FailureDiagnosis(
                failure_type="selector_not_found",
                failure_signal=self._signal(combined, "Selector did not match an element."),
                suspected_root_cause="The locator is stale, too brittle, scoped to the wrong container, or the target is rendered after the lookup.",
                repair_hint="Replace brittle locators with stable CSS, XPath text, role/aria, form labels, or container-scoped selectors and wait before locating.",
            )

        return FailureDiagnosis(
            failure_type="unknown_failure",
            failure_signal=self._signal(combined, "No known failure signature matched."),
            suspected_root_cause="The execution failed without a recognizable selector, wait, assertion, or safety signature.",
            repair_hint="Inspect stderr and stdout, preserve the user intent, add targeted waits and assertions, and keep the repair minimal.",
        )

    def _looks_like_selector_not_found(self, normalized: str) -> bool:
        return any(
            marker in normalized
            for marker in (
                "nosuchelementexception",
                "no such element",
                "unable to locate element",
                "could not locate element",
                "cannot locate element",
                "find_element",
            )
        )

    def _looks_like_wait_timeout(self, normalized: str) -> bool:
        return any(
            marker in normalized
            for marker in (
                "timeoutexception",
                "timed out",
                "execution timed out",
                "timeout while waiting",
                "waiting for",
                "wait until",
            )
        )

    def _looks_like_assertion_failure(self, normalized: str) -> bool:
        return any(
            marker in normalized
            for marker in (
                "assertionerror",
                "assert failed",
                "assert ",
                "expected",
                "actual",
            )
        )

    def _signal(self, text: str, fallback: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:500]
        return fallback
