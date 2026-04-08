from fastapi import APIRouter

from app.api.routes.executions import router as executions_router
from app.api.routes.generate import router as generate_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge import router as knowledge_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(generate_router)
api_router.include_router(executions_router)
api_router.include_router(knowledge_router)
