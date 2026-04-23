from pydantic import BaseModel, Field


class RuntimeSettingRead(BaseModel):
    key: str
    value: str
    updated_at: str


class RuntimeSettingsRead(BaseModel):
    execution_timeout_seconds: int = Field(ge=1, le=3600)
    max_self_heal_attempts: int = Field(ge=0, le=10)
    max_concurrent_executions: int = Field(ge=1, le=10)


class RuntimeSettingsUpdateRequest(BaseModel):
    execution_timeout_seconds: int = Field(ge=1, le=3600)
    max_self_heal_attempts: int = Field(ge=0, le=10)
    max_concurrent_executions: int = Field(ge=1, le=10)


class RuntimeSettingsResponse(BaseModel):
    status: str = "success"
    settings: RuntimeSettingsRead
    items: list[RuntimeSettingRead] = Field(default_factory=list)
