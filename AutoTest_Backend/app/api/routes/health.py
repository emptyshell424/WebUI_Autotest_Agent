from fastapi import APIRouter, Request

from app.core.container import get_container
from app.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def read_health(request: Request) -> HealthResponse:
    container = get_container(request)
    knowledge_status = container.rag.get_status()
    persisted_settings = container.system_settings.get_many(
        ["last_knowledge_rebuild_at", "execution_timeout_seconds", "model_name"]
    )

    model_ready = bool(container.settings.DEEPSEEK_API_KEY)
    health_status = "healthy" if model_ready and knowledge_status["ready"] else "degraded"

    return HealthResponse(
        status=health_status,
        backend={
            "status": "healthy",
            "details": {
                "app_name": container.settings.APP_NAME,
                "api_prefix": container.settings.API_V1_PREFIX,
            },
        },
        model={
            "status": "healthy" if model_ready else "degraded",
            "details": {
                "configured": model_ready,
                "provider": "DeepSeek-compatible OpenAI SDK",
                "model_name": persisted_settings.get("model_name", container.settings.MODEL_NAME),
                "base_url": container.settings.DEEPSEEK_BASE_URL,
            },
        },
        knowledge_base={
            "status": "healthy" if knowledge_status["ready"] else "degraded",
            "details": {
                **knowledge_status,
                "last_rebuild_at": persisted_settings.get("last_knowledge_rebuild_at"),
            },
        },
        storage={
            "status": "healthy",
            "details": {
                "database_path": str(container.settings.sqlite_db_path),
                "executions_dir": str(container.settings.executions_dir),
                "timeout_seconds": persisted_settings.get(
                    "execution_timeout_seconds",
                    str(container.settings.EXECUTION_TIMEOUT_SECONDS),
                ),
            },
        },
    )
