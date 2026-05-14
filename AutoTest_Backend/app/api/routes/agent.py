"""Agent API routes: /api/v1/agent/*"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.container import get_container
from app.schemas.agent import (
    AgentEventRead,
    AgentRunRequest,
    AgentRunResponse,
)
from app.services.agent_orchestrator import AgentEvent, AgentOrchestrator, AgentRunResult
from app.services.planner import Planner
from app.services.task_analyzer import TaskAnalyzer
from app.tools.base import ToolRegistry
from app.tools.diagnose_tool import DiagnoseFailureTool
from app.tools.execute_tool import ExecuteScriptTool, GetExecutionResultTool
from app.tools.generate_tool import GenerateScriptTool
from app.tools.knowledge_tool import SearchKnowledgeTool
from app.tools.memory_tool import SearchMemoryTool
from app.tools.repair_tool import RepairScriptTool
from app.tools.validate_tool import ValidateCodeTool
from app.services.adaptive_strategy_service import AdaptiveStrategyService
from app.services.intelligent_diagnostic_service import IntelligentDiagnosticService

logger = logging.getLogger("autotest.agent.api")

router = APIRouter(prefix="/agent", tags=["agent"])


def _build_tool_registry(container) -> ToolRegistry:
    """Wire up all tools from the DI container."""
    registry = ToolRegistry()
    registry.register(GenerateScriptTool(container.generation))
    registry.register(ExecuteScriptTool(container.execution_service))
    registry.register(GetExecutionResultTool(container.execution_service))
    registry.register(SearchKnowledgeTool(container.rag))
    registry.register(DiagnoseFailureTool(llm_service=container.llm))
    registry.register(ValidateCodeTool())
    adaptive = AdaptiveStrategyService(
        diagnostic_service=IntelligentDiagnosticService(
            llm_service=container.llm,
        ),
        memory_service=container.agent_memory,
    )
    registry.register(RepairScriptTool(
        container.llm, container.strategy,
        memory_service=container.agent_memory,
        adaptive_strategy_service=adaptive,
        site_profile_service=container.site_profile_service,
    ))
    registry.register(SearchMemoryTool(container.agent_memory))
    return registry


@router.post("/run", response_model=AgentRunResponse)
def agent_run(body: AgentRunRequest, request: Request) -> AgentRunResponse:
    """Execute the agent loop synchronously and return the full result."""
    container = get_container(request)
    registry = _build_tool_registry(container)
    task_analyzer = TaskAnalyzer(container.llm)
    planner = Planner(container.llm)
    orchestrator = AgentOrchestrator(
        settings=container.settings,
        llm_service=container.llm,
        tool_registry=registry,
        max_steps=body.max_steps,
        task_analyzer=task_analyzer,
        memory_service=container.agent_memory,
        planner=planner,
    )
    result: AgentRunResult = orchestrator.run(body.prompt)
    return AgentRunResponse(
        run_id=result.run_id,
        agent_status=result.status,
        steps=result.steps,
        test_case_id=result.memory.test_case_id,
        execution_id=result.memory.execution_id,
        error=result.error,
        events=[
            AgentEventRead(**e.to_dict()) for e in result.events
        ],
    )


@router.post("/run/stream")
def agent_run_stream(body: AgentRunRequest, request: Request) -> StreamingResponse:
    """Execute the agent loop and stream events via SSE."""
    container = get_container(request)
    registry = _build_tool_registry(container)

    import queue
    event_queue: queue.Queue[AgentEvent | None] = queue.Queue()

    def on_event(event: AgentEvent) -> None:
        event_queue.put(event)

    task_analyzer = TaskAnalyzer(container.llm)
    planner = Planner(container.llm)
    orchestrator = AgentOrchestrator(
        settings=container.settings,
        llm_service=container.llm,
        tool_registry=registry,
        max_steps=body.max_steps,
        on_event=on_event,
        task_analyzer=task_analyzer,
        memory_service=container.agent_memory,
        planner=planner,
    )

    # Hold the final result so we can emit it at the end
    result_holder: dict[str, Any] = {}

    def run_agent() -> None:
        try:
            result = orchestrator.run(body.prompt)
            result_holder["result"] = result
        except Exception as exc:
            logger.exception("Agent stream run failed")
            result_holder["error"] = str(exc)
        finally:
            event_queue.put(None)  # sentinel

    worker = threading.Thread(target=run_agent, daemon=True)
    worker.start()

    def event_generator():
        while True:
            event = event_queue.get()
            if event is None:
                # Send final summary
                if "result" in result_holder:
                    r = result_holder["result"]
                    summary = {
                        "event_type": "summary",
                        "run_id": r.run_id,
                        "status": r.status,
                        "steps": r.steps,
                        "test_case_id": r.memory.test_case_id,
                        "execution_id": r.memory.execution_id,
                        "error": r.error,
                    }
                    yield f"data: {json.dumps(summary, ensure_ascii=False)}\n\n"
                elif "error" in result_holder:
                    yield f"data: {json.dumps({'event_type': 'error', 'error': result_holder['error']}, ensure_ascii=False)}\n\n"
                break
            yield f"data: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
