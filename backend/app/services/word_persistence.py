from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.models import LexicalEntry


@dataclass
class EphemeralLexicalEntry:
    """Wynik enrichment bez zapisu do bazy (persist_words=false)."""

    id: UUID
    lemma_l2: str
    lemma_l1_primary: str | None
    pos: str | None
    content: dict
    lang_pair: str
    cefr: str | None = None
    source: str = "ai_ephemeral"
    usage_count: int = 0


def words_persistence_enabled() -> bool:
    return get_settings().persist_words


def build_ephemeral_entry(
    *,
    lang_pair: str,
    lemma_l2: str,
    lemma_l1_primary: str | None,
    pos: str | None,
    content: dict,
    cefr: str | None = None,
) -> EphemeralLexicalEntry:
    return EphemeralLexicalEntry(
        id=uuid4(),
        lang_pair=lang_pair,
        lemma_l2=lemma_l2,
        lemma_l1_primary=lemma_l1_primary,
        pos=pos,
        content=content,
        cefr=cefr,
    )
