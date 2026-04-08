from pydantic import BaseModel


class KnowledgeRebuildResponse(BaseModel):
    status: str = "success"
    ready: bool
    document_count: int
    chunk_count: int
    collection_name: str
