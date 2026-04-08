from app.core.config import Settings
from app.core.database import get_connection, utc_now_iso
from app.models import SettingRecord


class SettingsRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_many(self, keys: list[str]) -> dict[str, str]:
        if not keys:
            return {}
        placeholders = ", ".join("?" for _ in keys)
        with get_connection(self.settings) as connection:
            rows = connection.execute(
                f"SELECT key, value FROM system_setting WHERE key IN ({placeholders})",
                tuple(keys),
            ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    def upsert_many(self, values: dict[str, str]) -> None:
        timestamp = utc_now_iso()
        with get_connection(self.settings) as connection:
            for key, value in values.items():
                connection.execute(
                    """
                    INSERT INTO system_setting (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """,
                    (key, value, timestamp),
                )

    def list_all(self) -> list[SettingRecord]:
        with get_connection(self.settings) as connection:
            rows = connection.execute(
                "SELECT key, value, updated_at FROM system_setting ORDER BY key ASC"
            ).fetchall()
        return [SettingRecord(**dict(row)) for row in rows]
