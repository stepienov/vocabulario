# -*- coding: utf-8 -*-
"""Dla każdego (pl>es, lemma, pos) zostaw jeden najlepszy enrichment w cache i na kartach."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
_loaded: dict[str, str] = {}
for _line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    raw = _line.strip()
    if not raw or raw.startswith("#") or "=" not in raw:
        continue
    k, v = raw.split("=", 1)
    _loaded[k.strip()] = v.strip().strip('"').strip("'")
os.environ["DATABASE_URL"] = _loaded["PROD_DATABASE_URL"]
os.environ["ENVIRONMENT"] = "production"
os.environ.setdefault("JWT_SECRET", _loaded.get("JWT_SECRET", "unused"))
sys.path.insert(0, str(ROOT / "backend"))

PAIR = "pl>es"


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def _items(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict)]


def score_content(content: dict, *, pos: str, lemma: str) -> tuple:
    from app.ai.schemas.similar_words import MIN_SIMILAR_FOR_QUIZ, MIN_SIMILAR_WORDS
    from app.services.card_jobs import (
        _has_required_inflection,
        content_is_complete,
        content_is_learnable,
    )
    from app.services.enrichment import examples_complete
    from app.services.similar_words import sanitize_similar_words

    content = content or {}
    complete = int(content_is_complete(content, learning_lang="es"))
    learnable = int(content_is_learnable(content))
    infl = int(
        _has_required_inflection(
            content, pos=pos or "", lemma=lemma, learning_lang="es"
        )
    )
    similar = sanitize_similar_words(content.get("similar_words") or [], lemma, pos)
    similar_n = len(similar)
    quiz = int(similar_n >= MIN_SIMILAR_FOR_QUIZ)
    target12 = int(similar_n >= MIN_SIMILAR_WORDS)
    meanings = [m for m in (content.get("meanings") or []) if isinstance(m, dict)]
    ex_ok = 0
    cefr_ok = 0
    for m in meanings:
        examples = m.get("examples") or []
        if examples_complete(examples):
            cefr_ok += 1
        for ex in examples:
            if isinstance(ex, dict) and (ex.get("l2") or "").strip() and (ex.get("l1") or "").strip():
                ex_ok += 1
    ipa = int(bool((content.get("ipa") or "").strip()))
    syn = len(_items(content.get("synonyms_l2")))
    ant = len(_items(content.get("antonyms_l2")))
    fam = len(_items(content.get("word_family_l2")))
    assoc = len(_items(content.get("associations_l2")))
    return (
        complete,
        learnable,
        infl,
        quiz,
        target12,
        similar_n,
        cefr_ok,
        ex_ok,
        ipa,
        len(meanings),
        syn,
        ant,
        fam,
        assoc,
    )


async def main() -> None:
    from sqlalchemy import select, update

    from app.db.session import async_session_factory
    from app.models import LanguageProfile, LearningCard, LexicalEntry
    from app.services.card_jobs import apply_lexical_keys, content_is_complete, STATUS_READY

    async with async_session_factory() as db:
        profiles = (
            await db.execute(
                select(LanguageProfile.id).where(
                    LanguageProfile.app_lang == "pl",
                    LanguageProfile.learning_lang == "es",
                )
            )
        ).scalars().all()
        cards = (
            await db.execute(
                select(LearningCard).where(
                    LearningCard.profile_id.in_(profiles),
                    LearningCard.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        entries = (
            await db.execute(
                select(LexicalEntry).where(LexicalEntry.lang_pair == PAIR)
            )
        ).scalars().all()

        groups: dict[tuple[str, str], list[LearningCard]] = defaultdict(list)
        for c in cards:
            groups[(c.lemma_l2.lower(), (c.pos or "").lower())].append(c)

        entry_by: dict[tuple[str, str], LexicalEntry] = {}
        for e in entries:
            entry_by[(e.lemma_l2.lower(), (e.pos or "").lower())] = e

        changed = 0
        skipped_same = 0
        winners = {"cache": 0, "card": 0}
        now = datetime.now(UTC)

        for (lem_k, pos_k), group in groups.items():
            entry = entry_by.get((lem_k, pos_k))
            candidates: list[tuple[str, dict, datetime | None]] = []
            for c in group:
                candidates.append(("card", dict(c.content or {}), c.updated_at))
            if entry is not None:
                candidates.append(("cache", dict(entry.content or {}), entry.updated_at))

            unique = {dump(content) for _src, content, _ts in candidates}
            if len(unique) <= 1:
                skipped_same += 1
                continue

            lemma = group[0].lemma_l2
            pos = group[0].pos or ""
            ranked = sorted(
                candidates,
                key=lambda item: (
                    score_content(item[1], pos=pos, lemma=lemma),
                    item[2] or datetime(1970, 1, 1, tzinfo=UTC),
                ),
                reverse=True,
            )
            src, winner, _ = ranked[0]
            winner = dict(winner)
            winner["lemma"] = lemma
            winner["pos"] = pos
            winner["language"] = "es"
            winners["cache" if src == "cache" else "card"] += 1

            gloss = None
            meanings = winner.get("meanings") or []
            if meanings and isinstance(meanings[0], dict):
                gloss = meanings[0].get("gloss_l1")

            if entry is None:
                entry = LexicalEntry(
                    id=uuid4(),
                    lang_pair=PAIR,
                    lemma_l2=lemma,
                    lemma_l1_primary=gloss,
                    pos=pos or None,
                    content=winner,
                    source="ai",
                    usage_count=len(group),
                )
                apply_lexical_keys(entry)
                db.add(entry)
                await db.flush()
                entry_by[(lem_k, pos_k)] = entry
            else:
                entry.content = winner
                entry.lemma_l1_primary = gloss or entry.lemma_l1_primary
                entry.updated_at = now
                apply_lexical_keys(entry)

            ready = content_is_complete(winner, learning_lang="es")
            values = {
                "content": winner,
                "lexical_entry_id": entry.id,
                "gloss_primary": gloss,
                "updated_at": now,
            }
            if ready:
                values["enrichment_status"] = STATUS_READY
                values["enrichment_error"] = None
                values["enrichment_retry_count"] = 0
                values["enrichment_retry_at"] = None
            await db.execute(
                update(LearningCard)
                .where(LearningCard.id.in_([c.id for c in group]))
                .values(**values)
            )
            changed += 1

        await db.commit()
        print(
            f"groups={len(groups)} already_same={skipped_same} unified={changed} "
            f"winner_from={winners}",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
