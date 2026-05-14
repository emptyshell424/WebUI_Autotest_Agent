"""Pydantic schemas for the Agent API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    prompt: str = Field(min_length=5, description="Natural-language test scenario.")
    max_steps: int = Field(default=15, ge=1, le=30, description="Max agent loop steps.")


class AgentEventRead(BaseModel):
    event_type: str
    step: int
    data: dict = Field(default_factory=dict)
    timestamp: float


class AgentRunResponse(BaseModel):
    status: str = "success"
    run_id: str
    agent_status: str
    steps: int
    test_case_id: str | None = None
    execution_id: str | None = None
    error: str | None = None
    events: list[AgentEventRead] = Field(default_factory=list)


class AgentTraceResponse(BaseModel):
    run_id: str
    agent_status: str
    steps: int
    events: list[AgentEventRead] = Field(default_factory=list)
    memory: dict = Field(default_factory=dict)
