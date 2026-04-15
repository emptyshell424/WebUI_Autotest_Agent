from dataclasses import asdict

from fastapi import APIRouter, Request

from app.core.container import get_container
from app.schemas import GenerateRequest, GenerateResponse, TestCaseRead

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post("", response_model=GenerateResponse)
def generate_code(request_body: GenerateRequest, request: Request) -> GenerateResponse:
    container = get_container(request)
    case_record, rag_result = container.generation.generate(
        request_body.prompt,
        retrieval_mode=request_body.retrieval_mode,
    )
    return GenerateResponse(
        case=TestCaseRead(**asdict(case_record)),
        knowledge_sources=rag_result.sources,
        rag_result_count=rag_result.result_count,
        retrieval_mode=rag_result.retrieval_mode,
    )
