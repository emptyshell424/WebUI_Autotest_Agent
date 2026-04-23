from fastapi import APIRouter, Request

from app.core.container import get_container
from app.schemas import (
    RuntimeSettingRead,
    RuntimeSettingsRead,
    RuntimeSettingsResponse,
    RuntimeSettingsUpdateRequest,
)

router = APIRouter(prefix="/settings", tags=["settings"])

SETTING_KEYS = [
    "execution_timeout_seconds",
    "max_self_heal_attempts",
    "max_concurrent_executions",
]


def _build_runtime_settings(container) -> RuntimeSettingsRead:
    persisted = container.system_settings.get_many(SETTING_KEYS)
    return RuntimeSettingsRead(
        execution_timeout_seconds=int(
            persisted.get("execution_timeout_seconds", container.settings.EXECUTION_TIMEOUT_SECONDS)
        ),
        max_self_heal_attempts=int(
            persisted.get("max_self_heal_attempts", container.settings.MAX_SELF_HEAL_ATTEMPTS)
        ),
        max_concurrent_executions=int(
            persisted.get(
                "max_concurrent_executions",
                container.settings.MAX_CONCURRENT_EXECUTIONS,
            )
        ),
    )


@router.get("", response_model=RuntimeSettingsResponse)
def get_runtime_settings(request: Request) -> RuntimeSettingsResponse:
    container = get_container(request)
    items = [
        RuntimeSettingRead(key=item.key, value=item.value, updated_at=item.updated_at)
        for item in container.system_settings.list_all()
        if item.key in SETTING_KEYS
    ]
    return RuntimeSettingsResponse(settings=_build_runtime_settings(container), items=items)


@router.put("", response_model=RuntimeSettingsResponse)
def update_runtime_settings(
    request_body: RuntimeSettingsUpdateRequest,
    request: Request,
) -> RuntimeSettingsResponse:
    container = get_container(request)
    container.settings.EXECUTION_TIMEOUT_SECONDS = request_body.execution_timeout_seconds
    container.settings.MAX_SELF_HEAL_ATTEMPTS = request_body.max_self_heal_attempts
    container.settings.MAX_CONCURRENT_EXECUTIONS = request_body.max_concurrent_executions
    container.system_settings.upsert_many(
        {
            "execution_timeout_seconds": str(request_body.execution_timeout_seconds),
            "max_self_heal_attempts": str(request_body.max_self_heal_attempts),
            "max_concurrent_executions": str(request_body.max_concurrent_executions),
        }
    )
    items = [
        RuntimeSettingRead(key=item.key, value=item.value, updated_at=item.updated_at)
        for item in container.system_settings.list_all()
        if item.key in SETTING_KEYS
    ]
    return RuntimeSettingsResponse(settings=_build_runtime_settings(container), items=items)
