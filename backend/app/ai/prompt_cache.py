"""OpenAI GPT-5.6+ explicit prompt caching helpers."""

from __future__ import annotations

from typing import Any


def pair_cache_key(prefix: str, native: str, learning: str, *, extra: str = "") -> str:
    """Stable cache key per language pair (and optional suffix like CEFR)."""
    n, l = (native or "").strip().lower(), (learning or "").strip().lower()
    base = f"{prefix}:{n}>{l}"
    return f"{base}:{extra}" if extra else base


def cached_user_message(*, static: str, dynamic: str) -> list[dict[str, Any]]:
    """Static prefix first (cache breakpoint), dynamic suffix after."""
    return [
        {
            "type": "text",
            "text": static,
            "prompt_cache_breakpoint": {"mode": "explicit"},
        },
        {"type": "text", "text": dynamic},
    ]


def prompt_cache_request_options(*, cache_key: str) -> dict[str, Any]:
    return {
        "prompt_cache_key": cache_key,
        "prompt_cache_options": {"mode": "explicit", "ttl": "30m"},
    }
