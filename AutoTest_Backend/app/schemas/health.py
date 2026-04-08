from pydantic import BaseModel


class HealthSection(BaseModel):
    status: str
    details: dict[str, object]


class HealthResponse(BaseModel):
    status: str
    backend: HealthSection
    model: HealthSection
    knowledge_base: HealthSection
    storage: HealthSection
