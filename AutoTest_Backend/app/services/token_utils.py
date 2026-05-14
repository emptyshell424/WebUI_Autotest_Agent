"""Token estimation and context-window management utilities.

Provides lightweight heuristic token counting (no external tokenizer dependency)
and helper functions for truncating / compressing text to fit within a token budget.

Heuristic: for mixed CJK + Latin text the average is ~1.5 chars per token for CJK
and ~4 chars per token for ASCII.  We scan the text once and accumulate.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Rough chars-per-token ratios used by the heuristic estimator.
_CJK_CHARS_PER_TOKEN = 1.5
_ASCII_CHARS_PER_TOKEN = 4.0

# Regex matching CJK Unified Ideographs + common CJK punctuation ranges.
_CJK_RE = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef]"
)

# Default budget ceilings (tokens).
DEFAULT_CONTEXT_MAX_TOKENS = 4000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Return an *estimated* token count for *text*.

    The estimator is intentionally conservative (over-counts slightly) so that
    callers relying on it for budget enforcement are unlikely to exceed the
    real model context window.
    """
    if not text:
        return 0

    cjk_count = len(_CJK_RE.findall(text))
    ascii_count = len(text) - cjk_count

    tokens = cjk_count / _CJK_CHARS_PER_TOKEN + ascii_count / _ASCII_CHARS_PER_TOKEN
    # Add a small overhead for whitespace / special tokens.
    return max(1, int(tokens) + 1)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate *text* so its estimated token count is ≤ *max_tokens*.

    Returns the original text unchanged if it already fits.
    A trailing ``…`` is appended when truncation occurs.
    """
    if max_tokens <= 0:
        return ""
    if estimate_tokens(text) <= max_tokens:
        return text

    # Binary-search for the longest prefix that fits.
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if estimate_tokens(text[:mid]) <= max_tokens:
            lo = mid
        else:
            hi = mid - 1

    # Leave room for the ellipsis.
    cut = max(0, lo - 1)
    return text[:cut] + "…"


def allocate_budget(
    sections: list[tuple[str, str, int]],
    total_budget: int,
) -> list[tuple[str, str]]:
    """Fit labelled text sections into a total token budget.

    *sections* is a list of ``(label, text, priority)`` tuples where lower
    ``priority`` numbers are kept first.  Returns ``[(label, possibly_truncated_text), ...]``
    for sections that fit (at least partially) within *total_budget*.

    Allocation strategy:
    1. Sort by priority (ascending = most important first).
    2. Walk sections in priority order; each section gets up to the remaining
       budget.  If a section is too large it is truncated; if there is zero
       budget left the section is dropped.
    """
    if total_budget <= 0:
        return []

    ordered = sorted(sections, key=lambda s: s[2])
    result: list[tuple[str, str]] = []
    remaining = total_budget

    for label, text, _prio in ordered:
        if remaining <= 0:
            break
        est = estimate_tokens(text)
        if est <= remaining:
            result.append((label, text))
            remaining -= est
        else:
            truncated = truncate_to_tokens(text, remaining)
            if truncated:
                result.append((label, truncated))
            remaining = 0

    return result
