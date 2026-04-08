from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.core.container import get_container
from app.schemas import KnowledgeRebuildResponse

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/rebuild", response_model=KnowledgeRebuildResponse)
def rebuild_knowledge_base(request: Request) -> KnowledgeRebuildResponse:
    container = get_container(request)
    result = container.rag.rebuild_index()
    container.system_settings.upsert_many(
        {
            "last_knowledge_rebuild_at": datetime.now(timezone.utc).isoformat(),
            "last_knowledge_document_count": str(result["document_count"]),
            "last_knowledge_chunk_count": str(result["chunk_count"]),
        }
    )
    return KnowledgeRebuildResponse(**result)
