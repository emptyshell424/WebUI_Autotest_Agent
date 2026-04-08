from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=5)


class TestCaseRead(BaseModel):
    id: str
    title: str
    prompt: str
    generated_code: str
    raw_output: str
    rag_context: str
    status: str
    created_at: str


class GenerateResponse(BaseModel):
    status: str = "success"
    case: TestCaseRead
    knowledge_sources: list[str]
    rag_result_count: int
