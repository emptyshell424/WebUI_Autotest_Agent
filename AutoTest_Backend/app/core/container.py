from dataclasses import dataclass

from fastapi import Request

from app.core.config import Settings, get_settings
from app.core.database import initialize_database
from app.repositories import ExecutionRepository, SettingsRepository, TestCaseRepository
from app.services import (
    ExecutionService,
    GenerationService,
    LLMService,
    RAGService,
    StrategyService,
)


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    test_cases: TestCaseRepository
    executions: ExecutionRepository
    system_settings: SettingsRepository
    llm: LLMService
    rag: RAGService
    strategy: StrategyService
    generation: GenerationService
    execution_service: ExecutionService


def create_container(settings: Settings | None = None) -> ServiceContainer:
    active_settings = settings or get_settings()
    initialize_database(active_settings)

    test_cases = TestCaseRepository(active_settings)
    executions = ExecutionRepository(active_settings)
    system_settings = SettingsRepository(active_settings)
    persisted_settings = system_settings.get_many(
        [
            "execution_timeout_seconds",
            "max_self_heal_attempts",
            "max_concurrent_executions",
        ]
    )
    if "execution_timeout_seconds" in persisted_settings:
        active_settings.EXECUTION_TIMEOUT_SECONDS = int(persisted_settings["execution_timeout_seconds"])
    if "max_self_heal_attempts" in persisted_settings:
        active_settings.MAX_SELF_HEAL_ATTEMPTS = int(persisted_settings["max_self_heal_attempts"])
    if "max_concurrent_executions" in persisted_settings:
        active_settings.MAX_CONCURRENT_EXECUTIONS = int(
            persisted_settings["max_concurrent_executions"]
        )
    rag = RAGService(active_settings)
    llm = LLMService(active_settings)
    strategy = StrategyService()
    generation = GenerationService(llm, rag, test_cases, strategy)
    executions.recover_interrupted_executions()
    execution_service = ExecutionService(active_settings, executions, test_cases, llm, strategy)

    system_settings.upsert_many(
        {
            "execution_timeout_seconds": str(active_settings.EXECUTION_TIMEOUT_SECONDS),
            "max_self_heal_attempts": str(active_settings.MAX_SELF_HEAL_ATTEMPTS),
            "max_concurrent_executions": str(active_settings.MAX_CONCURRENT_EXECUTIONS),
            "knowledge_base_dir": str(active_settings.knowledge_base_dir),
            "model_name": active_settings.MODEL_NAME,
        }
    )

    return ServiceContainer(
        settings=active_settings,
        test_cases=test_cases,
        executions=executions,
        system_settings=system_settings,
        llm=llm,
        rag=rag,
        strategy=strategy,
        generation=generation,
        execution_service=execution_service,
    )


def get_container(request: Request) -> ServiceContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        settings = getattr(request.app.state, "settings", None) or get_settings()
        container = create_container(settings)
        request.app.state.container = container
    return container
