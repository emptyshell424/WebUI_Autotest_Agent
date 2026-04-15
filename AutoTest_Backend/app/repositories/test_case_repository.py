import uuid

from app.core.config import Settings
from app.core.database import get_connection, utc_now_iso
from app.models import TestCaseRecord


class TestCaseRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(
        self,
        *,
        title: str,
        prompt: str,
        generated_code: str,
        raw_output: str,
        rag_context: str,
        requested_strategy: str,
        effective_strategy: str,
        status: str = "generated",
    ) -> TestCaseRecord:
        record = TestCaseRecord(
            id=str(uuid.uuid4()),
            title=title,
            prompt=prompt,
            generated_code=generated_code,
            raw_output=raw_output,
            rag_context=rag_context,
            status=status,
            created_at=utc_now_iso(),
            requested_strategy=requested_strategy,
            effective_strategy=effective_strategy,
        )
        with get_connection(self.settings) as connection:
            connection.execute(
                """
                INSERT INTO test_case (
                    id, title, prompt, generated_code, raw_output, rag_context, status,
                    created_at, requested_strategy, effective_strategy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.title,
                    record.prompt,
                    record.generated_code,
                    record.raw_output,
                    record.rag_context,
                    record.status,
                    record.created_at,
                    record.requested_strategy,
                    record.effective_strategy,
                ),
            )
        return record

    def get(self, test_case_id: str) -> TestCaseRecord | None:
        with get_connection(self.settings) as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    title,
                    prompt,
                    generated_code,
                    raw_output,
                    rag_context,
                    status,
                    created_at,
                    requested_strategy,
                    effective_strategy
                FROM test_case
                WHERE id = ?
                """,
                (test_case_id,),
            ).fetchone()
        if row is None:
            return None
        return TestCaseRecord(**dict(row))

    def update_status(self, test_case_id: str, status: str) -> None:
        with get_connection(self.settings) as connection:
            connection.execute(
                "UPDATE test_case SET status = ? WHERE id = ?",
                (status, test_case_id),
            )
