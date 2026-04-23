from dataclasses import dataclass


@dataclass(slots=True)
class TestCaseRecord:
    id: str
    title: str
    prompt: str
    generated_code: str
    raw_output: str
    rag_context: str
    status: str
    created_at: str
    requested_strategy: str
    effective_strategy: str


@dataclass(slots=True)
class ExecutionRecord:
    id: str
    test_case_id: str
    executed_code: str
    status: str
    run_directory: str | None
    script_path: str | None
    logs: str | None
    error: str | None
    validation_errors: list[str]
    created_at: str
    started_at: str | None
    finished_at: str | None
    requested_strategy: str
    effective_strategy: str
    fallback_reason: str | None
    site_profile: str | None
    test_case_title: str | None = None
    self_heal_triggered: bool = False
    self_heal_count: int = 0
    healed: bool = False
    self_heal_attempts: list["SelfHealAttemptRecord"] | None = None


@dataclass(slots=True)
class SelfHealAttemptRecord:
    id: str
    execution_id: str
    attempt_number: int
    status: str
    failure_reason: str | None
    repair_summary: str | None
    original_code: str
    repaired_code: str | None
    logs: str | None
    error: str | None
    validation_errors: list[str]
    run_directory: str | None
    script_path: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    strategy_before: str
    strategy_after: str
    fallback_reason: str | None
    site_profile: str | None


@dataclass(slots=True)
class SettingRecord:
    key: str
    value: str
    updated_at: str


@dataclass(slots=True)
class ExecutionTrendPoint:
    bucket: str
    execution_count: int
    completed_count: int
    healed_completed_count: int
    failed_count: int
    blocked_count: int
    final_success_rate: float
