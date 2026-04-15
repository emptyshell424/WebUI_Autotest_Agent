from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=5)
    retrieval_mode: str | None = Field(default=None)


class TestCaseRead(BaseModel):
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


class GenerateResponse(BaseModel):
    status: str = "success"
    case: TestCaseRead
    knowledge_sources: list[str]
    rag_result_count: int
    retrieval_mode: str
