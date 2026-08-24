from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from fastapi import Request

NAV = [
    ("overview", "/admin", "Przegląd"),
    ("users", "/admin/users", "Użytkownicy"),
    ("lists", "/admin/lists", "Listy"),
    ("cards", "/admin/cards", "Słowa"),
    ("lookups", "/admin/lookups", "Wyszukiwania"),
    ("reviews", "/admin/reviews", "Powtórki"),
    ("costs", "/admin/costs", "Koszty LLM"),
    ("errors", "/admin/errors", "Błędy"),
    ("imports", "/admin/imports", "Importy"),
]

STATUS_LABELS = {
    "pending": "w toku",
    "preparing": "przygotowanie",
    "ready": "gotowe",
    "failed": "błąd",
    "prep_problem": "problem",
    "learnable": "do nauki",
    "ok": "ok",
    "error": "błąd",
    "warn": "ostrzeżenie",
    "info": "info",
    "new": "nowe",
    "learning": "nauka",
    "review": "powtórka",
    "relearning": "ponownie",
}

STATUS_TONE = {
    "ready": "ok",
    "ok": "ok",
    "learnable": "ok",
    "pending": "warn",
    "preparing": "warn",
    "info": "warn",
    "warn": "warn",
    "failed": "err",
    "error": "err",
    "prep_problem": "err",
}


def fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%d.%m.%Y %H:%M")


def fmt_usd(value: Decimal | float | None) -> str:
    if value is None:
        return "—"
    number = float(value)
    if number == 0:
        return "$0.00"
    if abs(number) < 0.01:
        return f"${number:.4f}"
    return f"${number:.2f}"


def fmt_int(value: int | None) -> str:
    return f"{int(value or 0):,}".replace(",", " ")


def status_label(raw: str | None) -> str:
    key = (raw or "").strip().lower()
    return STATUS_LABELS.get(key, raw or "—")


def status_tone(raw: str | None) -> str:
    return STATUS_TONE.get((raw or "").strip().lower(), "")


def parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        if len(text) == 10:
            return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=UTC)
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def as_uuid(raw: str | None) -> UUID | None:
    if not raw:
        return None
    try:
        return UUID(raw.strip())
    except ValueError:
        return None


def qs(request: Request, **updates: Any) -> str:
    params: dict[str, str] = dict(request.query_params)
    for key, value in updates.items():
        if value is None or value == "":
            params.pop(key, None)
        else:
            params[key] = str(value)
    encoded = urlencode(params)
    return f"?{encoded}" if encoded else ""


def page_offset(page: int, size: int) -> int:
    return max(0, (max(1, page) - 1) * size)
