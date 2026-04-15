from dataclasses import asdict

from fastapi import APIRouter, Request

from app.core.container import get_container
from app.core.exceptions import AppError
from app.schemas import TestCaseRead

router = APIRouter(prefix="/test-cases", tags=["test-cases"])


@router.get("/{test_case_id}", response_model=TestCaseRead)
def get_test_case(test_case_id: str, request: Request) -> TestCaseRead:
    container = get_container(request)
    record = container.test_cases.get(test_case_id)
    if record is None:
        raise AppError(
            "Test case was not found.",
            status_code=404,
            code="test_case_not_found",
        )
    return TestCaseRead(**asdict(record))
