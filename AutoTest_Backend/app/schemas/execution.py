from pydantic import BaseModel


class ExecutionCreateRequest(BaseModel):
    test_case_id: str
    code_override: str | None = None


class SelfHealAttemptRead(BaseModel):
    id: str
    execution_id: str
    attempt_number: int
    status: str
    failure_reason: str | None = None
    repair_summary: str | None = None
    original_code: str
    repaired_code: str | None = None
    logs: str | None = None
    error: str | None = None
    validation_errors: list[str] = []
    run_directory: str | None = None
    script_path: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


class ExecutionRead(BaseModel):
    id: str
    test_case_id: str
    test_case_title: str | None = None
    executed_code: str
    status: str
    run_directory: str | None = None
    script_path: str | None = None
    logs: str | None = None
    error: str | None = None
    validation_errors: list[str] = []
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    self_heal_triggered: bool = False
    self_heal_count: int = 0
    healed: bool = False
    self_heal_attempts: list[SelfHealAttemptRead] = []


class ExecutionListResponse(BaseModel):
    status: str = "success"
    items: list[ExecutionRead]
    limit: int
    offset: int


class ExecutionStatsRead(BaseModel):
    generated_count: int
    execution_count: int
    effective_execution_count: int
    first_pass_success_count: int
    self_heal_triggered_count: int
    self_heal_success_count: int
    final_success_count: int
    first_pass_success_rate: float
    self_heal_triggered_rate: float
    self_heal_success_rate: float
    final_success_rate: float


class ExecutionStatsResponse(BaseModel):
    status: str = "success"
    metrics: ExecutionStatsRead
