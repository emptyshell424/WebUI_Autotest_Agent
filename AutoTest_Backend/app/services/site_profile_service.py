"""Site profile service: build and maintain per-site execution profiles.

Each site (identified by domain / netloc) accumulates execution statistics,
known selectors, failure patterns, and successful strategies over time.
Profiles are stored as lightweight JSON files, one per domain.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger("autotest.site_profile")

# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass
class SiteProfile:
    """Accumulated profile for a single site (domain)."""

    site_url: str
    known_selectors: dict[str, list[str]] = field(default_factory=dict)
    page_load_patterns: dict[str, str] = field(default_factory=dict)
    common_failure_patterns: list[str] = field(default_factory=list)
    successful_strategies: list[str] = field(default_factory=list)
    execution_count: int = 0
    success_count: int = 0
    last_updated: str = ""

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SiteProfile:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Selector extraction helpers
# ---------------------------------------------------------------------------

_CSS_SELECTOR_RE = re.compile(
    r"(?:#[\w-]+|\.[\w-]+|(?:input|button|select|textarea|a|div|span|form)\[[\w-]+(?:=[^\]]+)?\])"
)


def _extract_selectors_from_text(text: str) -> list[str]:
    """Best-effort extraction of CSS-like selectors from error/log text."""
    return _CSS_SELECTOR_RE.findall(text) if text else []


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

_MAX_FAILURE_PATTERNS = 50
_MAX_SUCCESSFUL_STRATEGIES = 30
_MAX_KNOWN_SELECTORS_PER_KEY = 10


class SiteProfileService:
    """Manage per-site profiles stored as ``{netloc}.json`` files."""

    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # URL normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Extract the netloc (domain + optional port) from *url*."""
        if not url:
            return ""
        # Ensure scheme is present so urlparse works correctly.
        if "://" not in url:
            url = "http://" + url
        netloc = urlparse(url).netloc
        return netloc.lower() if netloc else ""

    def _profile_path(self, netloc: str) -> Path:
        # Replace characters unsafe for filenames.
        safe = netloc.replace(":", "_")
        return self._storage_dir / f"{safe}.json"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get_profile(self, url: str) -> SiteProfile | None:
        """Load the profile for the site identified by *url*.

        Returns ``None`` if no profile exists yet.
        """
        netloc = self._normalize_url(url)
        if not netloc:
            return None
        path = self._profile_path(netloc)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return SiteProfile.from_dict(data)
        except (json.JSONDecodeError, TypeError, KeyError):
            logger.warning("Corrupted profile for %s – ignoring", netloc)
            return None

    def save_profile(self, profile: SiteProfile) -> None:
        """Persist *profile* to its JSON file."""
        netloc = self._normalize_url(profile.site_url)
        if not netloc:
            logger.warning("Cannot save profile with empty site_url")
            return
        path = self._profile_path(netloc)
        path.write_text(
            json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug("Saved site profile for %s", netloc)

    # ------------------------------------------------------------------
    # Incremental update
    # ------------------------------------------------------------------

    def update_from_execution(
        self,
        url: str,
        status: str,
        error: str = "",
        logs: str = "",
        diagnosis: str = "",
        strategy: str = "",
    ) -> SiteProfile:
        """Update (or create) a site profile after one execution run.

        Parameters
        ----------
        url:
            Target URL of the execution.
        status:
            ``"success"`` or ``"failure"`` (or any non-``"success"`` value).
        error / logs / diagnosis:
            Textual information from the execution; used to extract failure
            patterns and selectors.
        strategy:
            The strategy name that was used in this execution.

        Returns the updated profile.
        """
        profile = self.get_profile(url) or SiteProfile(
            site_url=self._normalize_url(url),
        )

        profile.execution_count += 1
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        profile.last_updated = now

        is_success = status.lower() == "success" if status else False

        if is_success:
            profile.success_count += 1
            if strategy and strategy not in profile.successful_strategies:
                profile.successful_strategies.append(strategy)
                profile.successful_strategies = profile.successful_strategies[
                    -_MAX_SUCCESSFUL_STRATEGIES:
                ]
        else:
            # Append failure pattern (deduplicated, capped).
            failure_snippet = self._build_failure_snippet(error, diagnosis)
            if failure_snippet and failure_snippet not in profile.common_failure_patterns:
                profile.common_failure_patterns.append(failure_snippet)
                profile.common_failure_patterns = profile.common_failure_patterns[
                    -_MAX_FAILURE_PATTERNS:
                ]

        # Extract and merge selectors from error / logs.
        combined_text = f"{error} {logs} {diagnosis}"
        new_selectors = _extract_selectors_from_text(combined_text)
        if new_selectors:
            key = "auto_extracted"
            existing = profile.known_selectors.get(key, [])
            for sel in new_selectors:
                if sel not in existing:
                    existing.append(sel)
            profile.known_selectors[key] = existing[-_MAX_KNOWN_SELECTORS_PER_KEY:]

        self.save_profile(profile)
        return profile

    @staticmethod
    def _build_failure_snippet(error: str, diagnosis: str) -> str:
        """Build a concise failure pattern string."""
        parts: list[str] = []
        if error:
            # Take at most the first 120 chars of the error.
            parts.append(error[:120].strip())
        if diagnosis:
            parts.append(diagnosis[:120].strip())
        return " | ".join(parts)

    # ------------------------------------------------------------------
    # Prompt generation
    # ------------------------------------------------------------------

    def get_profile_prompt_block(self, url: str, max_chars: int = 2000) -> str:
        """Return a text block suitable for LLM prompt injection.

        Returns an empty string when no profile exists.
        """
        profile = self.get_profile(url)
        if profile is None:
            return ""

        lines: list[str] = [f"Site: {profile.site_url}"]
        lines.append(
            f"Executions: {profile.execution_count}  "
            f"Successes: {profile.success_count}  "
            f"Last updated: {profile.last_updated}"
        )

        if profile.known_selectors:
            lines.append("Known selectors:")
            for key, sels in profile.known_selectors.items():
                lines.append(f"  {key}: {', '.join(sels)}")

        if profile.page_load_patterns:
            lines.append("Page load patterns:")
            for k, v in profile.page_load_patterns.items():
                lines.append(f"  {k}: {v}")

        if profile.common_failure_patterns:
            lines.append("Common failures:")
            for pat in profile.common_failure_patterns:
                lines.append(f"  - {pat}")

        if profile.successful_strategies:
            lines.append(f"Successful strategies: {', '.join(profile.successful_strategies)}")

        block = "\n".join(lines)
        if len(block) > max_chars:
            block = block[: max_chars - 3] + "..."
        return block
