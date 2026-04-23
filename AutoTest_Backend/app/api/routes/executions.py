from dataclasses import asdict

from fastapi import APIRouter, Query, Request

from app.core.container import get_container
from app.schemas import (
    ExecutionCreateRequest,
    ExecutionListResponse,
    ExecutionRead,
    ExecutionStatsRead,
    ExecutionStatsResponse,
)

router = APIRouter(prefix="/executions", tags=["executions"])


@router.post("", response_model=ExecutionRead)
def create_execution(request_body: ExecutionCreateRequest, request: Request) -> ExecutionRead:
    container = get_container(request)
    record = container.execution_service.create_execution(
        test_case_id=request_body.test_case_id,
        code_override=request_body.code_override,
    )
    return ExecutionRead(**asdict(record))


@router.get("/stats", response_model=ExecutionStatsResponse)
def get_execution_stats(request: Request) -> ExecutionStatsResponse:
    container = get_container(request)
    return ExecutionStatsResponse(metrics=ExecutionStatsRead(**container.execution_service.get_stats()))


@router.get("", response_model=ExecutionListResponse)
def list_executions(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
) -> ExecutionListResponse:
    container = get_container(request)
    items = [
        ExecutionRead(**asdict(record))
        for record in container.execution_service.list_executions(limit=limit, offset=offset, status=status)
    ]
    return ExecutionListResponse(
        items=items,
        limit=limit,
        offset=offset,
        total=container.execution_service.count_executions(status=status),
        status_filter=status,
    )


@router.delete("/{execution_id}", response_model=ExecutionRead)
def cancel_execution(execution_id: str, request: Request) -> ExecutionRead:
    container = get_container(request)
    record = container.execution_service.cancel_execution(execution_id)
    return ExecutionRead(**asdict(record))


@router.get("/{execution_id}", response_model=ExecutionRead)
def get_execution(execution_id: str, request: Request) -> ExecutionRead:
    container = get_container(request)
    record = container.execution_service.get_execution(execution_id)
    return ExecutionRead(**asdict(record))
