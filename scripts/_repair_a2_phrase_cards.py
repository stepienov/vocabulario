# -*- coding: utf-8 -*-
"""Naprawia zepsute frazy A2 w cache (pl>es) — karta musi stać sama, bez słów usera."""
from __future__ import annotations

import asyncio
import os
import sys
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
os.environ["DEBUG"] = "false"
os.environ["LLM_MOCK"] = "false"
os.environ["PERSIST_WORDS"] = "true"
os.environ.setdefault("OPENAI_API_KEY", _loaded.get("OPENAI_API_KEY", ""))
os.environ.setdefault("LLM_PROVIDER", _loaded.get("LLM_PROVIDER", "openai"))
os.environ.setdefault("LLM_LOOKUP_MODEL", _loaded.get("LLM_LOOKUP_MODEL", "gpt-5.6-terra"))
os.environ.setdefault("LLM_ENRICHMENT_MODEL", _loaded.get("LLM_ENRICHMENT_MODEL", "gpt-5.6-terra"))
os.environ.setdefault("LLM_LIGHT_MODEL", _loaded.get("LLM_LIGHT_MODEL", "gpt-5.6-luna"))
os.environ.setdefault("JWT_SECRET", _loaded.get("JWT_SECRET", "unused"))
sys.path.insert(0, str(ROOT / "backend"))

LEMMAS = (
    "pedir perdón",
    "tener prisa",
    "tener sueño",
    "tener hambre",
    "tener miedo",
    "seguro de sí mismo",
    "quedarse dormido",
)


def _same_pos_similar(content: dict) -> list[dict]:
    from app.services.similar_words import sanitize_similar_words

    lemma = content.get("lemma") or ""
    pos = content.get("pos")
    return sanitize_similar_words(content.get("similar_words") or [], lemma, pos)


async def repair_content(profile, content: dict, llm) -> dict:
    from app.ai.schemas.similar_words import MIN_SIMILAR_WORDS
    from app.lsp.enrichment import fetch_lsp_inflection, merge_side_jobs
    from app.services.card_jobs import _has_verb_inflection, inflect_pos_key
    from app.services.enrichment import (
        _merge_examples_into_meanings,
        examples_complete,
    )
    from app.services.similar_words import fetch_similar_words

    content = dict(content)
    lemma = content.get("lemma") or ""
    pos = content.get("pos")
    similar = _same_pos_similar(content)
    if len(similar) < MIN_SIMILAR_WORDS:
        similar = await fetch_similar_words(llm, profile, lemma, pos)
        if len(similar) < MIN_SIMILAR_WORDS:
            extra = await fetch_similar_words(llm, profile, lemma, pos)
            seen = {s["lemma"].lower() for s in similar}
            for item in extra:
                key = item["lemma"].lower()
                if key in seen:
                    continue
                similar.append(item)
                seen.add(key)
                if len(similar) >= MIN_SIMILAR_WORDS:
                    break
        content["similar_words"] = similar[:MIN_SIMILAR_WORDS]
    else:
        content["similar_words"] = similar

    need_infl = (
        inflect_pos_key(pos, lemma=lemma, learning_lang=profile.learning_lang) is not None
        and not _has_verb_inflection(content)
    )
    if need_infl:
        inflection = await fetch_lsp_inflection(llm, profile, lemma, pos)
        content = merge_side_jobs(
            content, content.get("similar_words"), inflection, profile
        )

    meanings = [m for m in (content.get("meanings") or []) if isinstance(m, dict)]
    if meanings and not all(examples_complete(m.get("examples") or []) for m in meanings):
        glosses = [m["gloss_l1"] for m in meanings if m.get("gloss_l1")]
        payload = await llm.generate_examples(
            lemma=lemma,
            pos=pos,
            glosses=glosses,
            native=profile.app_lang,
            learning=profile.learning_lang,
            retry=True,
        )
        _merge_examples_into_meanings(content, payload)

    return content


async def main() -> None:
    from sqlalchemy import select, update

    from app.core.deps import lang_pair_key
    from app.db.session import async_session_factory
    from app.models import LanguageProfile, LearningCard, LexicalEntry, User
    from app.services.card_jobs import content_is_complete
    from app.services.distractors import quiz_pos_matches
    from app.services.llm import LLMService
    from app.services.llm_usage import bind_llm_usage_context

    llm = LLMService()
    async with async_session_factory() as db:
        profile = (
            await db.execute(
                select(LanguageProfile)
                .join(User, User.id == LanguageProfile.user_id)
                .where(User.email == "alextest@test.pl")
            )
        ).scalar_one()
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        entries = (
            await db.execute(
                select(LexicalEntry).where(
                    LexicalEntry.lang_pair == pair,
                    LexicalEntry.lemma_l2.in_(LEMMAS),
                )
            )
        ).scalars().all()
        phrase_entries = {
            e.lemma_l2: e for e in entries if (e.pos or "").lower() == "phrase"
        }
        print(
            f"phrase_cache={sorted(phrase_entries)} "
            f"missing={sorted(set(LEMMAS) - set(phrase_entries))}",
            flush=True,
        )

        repaired: dict[str, dict] = {}
        for lemma in LEMMAS:
            entry = phrase_entries.get(lemma)
            if entry is None:
                card = (
                    await db.execute(
                        select(LearningCard).where(
                            LearningCard.lemma_l2 == lemma,
                            LearningCard.deleted_at.is_(None),
                            LearningCard.profile_id == profile.id,
                            LearningCard.pos == "phrase",
                        )
                    )
                ).scalar_one_or_none()
                if card is None:
                    print(f"SKIP no row {lemma!r}", flush=True)
                    continue
                seed = dict(card.content or {})
            else:
                seed = dict(entry.content or {})
            seed["lemma"] = lemma
            seed["pos"] = "phrase"
            bind_llm_usage_context(
                overwrite_operation=True,
                operation_id=uuid4(),
                operation_kind="lemma_enrich",
                lemma=lemma,
                pos="phrase",
                lang_pair=pair,
            )
            print(f"repair {lemma!r} pos=phrase", flush=True)
            repaired[lemma] = await repair_content(profile, seed, llm)
            repaired[lemma]["lemma"] = lemma
            repaired[lemma]["pos"] = "phrase"

        now = datetime.now(UTC)
        profile_ids = (
            await db.execute(
                select(LanguageProfile.id).where(
                    LanguageProfile.app_lang == profile.app_lang,
                    LanguageProfile.learning_lang == profile.learning_lang,
                )
            )
        ).scalars().all()

        for lemma, content in repaired.items():
            similar = content.get("similar_words") or []
            exact = [
                s
                for s in similar
                if quiz_pos_matches(content.get("pos"), s.get("pos"), family=False)
            ]
            complete = content_is_complete(content, learning_lang=profile.learning_lang)
            print(
                f"  {lemma!r} complete={complete} similar={len(similar)} "
                f"same_pos={len(exact)} infl_verbs={bool((content.get('inflection') or {}).get('verbs'))}",
                flush=True,
            )
            if not complete or len(exact) < 7:
                raise SystemExit(f"still incomplete: {lemma}")

            entry = phrase_entries.get(lemma)
            if entry is not None:
                entry.content = content
                entry.pos = "phrase"
                entry.lemma_l1_primary = (content.get("meanings") or [{}])[0].get("gloss_l1")
                entry.updated_at = now
                await db.flush()
                entry_id = entry.id
            else:
                entry = LexicalEntry(
                    lang_pair=pair,
                    lemma_l2=lemma,
                    lemma_l1_primary=(content.get("meanings") or [{}])[0].get("gloss_l1"),
                    pos="phrase",
                    cefr=profile.cefr_level,
                    content=content,
                    source="ai",
                    usage_count=1,
                )
                db.add(entry)
                await db.flush()
                entry_id = entry.id
                phrase_entries[lemma] = entry

            await db.execute(
                update(LearningCard)
                .where(
                    LearningCard.lemma_l2 == lemma,
                    LearningCard.deleted_at.is_(None),
                    LearningCard.profile_id.in_(profile_ids),
                    LearningCard.pos == "phrase",
                )
                .values(
                    content=content,
                    gloss_primary=(content.get("meanings") or [{}])[0].get("gloss_l1"),
                    enrichment_status="ready",
                    enrichment_error=None,
                    enrichment_retry_count=0,
                    enrichment_retry_at=None,
                    lexical_entry_id=entry_id,
                    updated_at=now,
                )
            )
        await db.commit()
        print("ok", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
