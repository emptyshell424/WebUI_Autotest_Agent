from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.container import create_container
from app.core.exceptions import AppError
from app.core.logger import setup_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    setup_logging()
    active_settings = settings or get_settings()
    app = FastAPI(title=active_settings.APP_NAME)
    app.state.settings = active_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.FRONTEND_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    app.include_router(api_router, prefix=active_settings.API_V1_PREFIX)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
