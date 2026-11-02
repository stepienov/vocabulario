# -*- coding: utf-8 -*-
"""Jeden UPDATE + jeden INSERT na produkcji — bez pętli po kartach."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

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

EMAIL = "alextest@test.pl"
A2_NAMES = (
    "a2 1-10",
    "a2 11-20",
    "a2 21-30",
    "a2 31-40",
    "a2 41-50",
    "a2 51-60",
    "a2 61-70",
    "a2 71-80",
)

PROMOTE = """
WITH target AS (
    SELECT lc.id
    FROM learning_cards lc
    JOIN word_lists wl ON wl.id = lc.deck_id
    JOIN users u ON u.id = lc.user_id
    WHERE u.email = :email
      AND wl.deleted_at IS NULL
      AND wl.name IN :names
      AND lc.deleted_at IS NULL
      AND lc.enrichment_status = 'learnable'
      AND jsonb_array_length(COALESCE(lc.content->'similar_words', '[]'::jsonb)) >= 12
      AND (
            (
                lower(COALESCE(lc.pos, '')) = 'noun'
                AND jsonb_typeof(lc.content#>'{inflection,nouns}') = 'object'
                AND lc.content#>'{inflection,nouns}' <> '{}'::jsonb
            )
         OR (
                lower(COALESCE(lc.pos, '')) IN ('adj', 'adjective')
                AND jsonb_typeof(lc.content#>'{inflection,adjectives}') = 'object'
                AND lc.content#>'{inflection,adjectives}' <> '{}'::jsonb
            )
         OR (
                lower(COALESCE(lc.pos, '')) IN ('verb', 'phrase')
                AND (
                    (lc.content->'conjugation' IS NOT NULL AND lc.content->'conjugation' <> 'null'::jsonb)
                    OR lc.content#>'{inflection,verbs,tenses}' IS NOT NULL
                    OR lc.content#>'{inflection,verbs,non_finite}' IS NOT NULL
                )
            )
      )
)
UPDATE learning_cards lc
SET enrichment_status = 'ready',
    enrichment_retry_count = 0,
    enrichment_retry_at = NULL,
    enrichment_error = NULL,
    updated_at = now()
FROM target
WHERE lc.id = target.id
RETURNING lc.id
"""

CACHE_INSERT = """
INSERT INTO lexical_entries (
    id, lang_pair, lemma_l2, lemma_l1_primary, pos, cefr, content,
    source, created_by_user_id, usage_count
)
SELECT
    gen_random_uuid(),
    lp.app_lang || '>' || lp.learning_lang,
    lc.lemma_l2,
    COALESCE(lc.gloss_primary, lc.content#>>'{meanings,0,gloss_l1}'),
    lc.pos,
    lp.cefr_level,
    lc.content,
    'ai',
    lc.user_id,
    1
FROM learning_cards lc
JOIN word_lists wl ON wl.id = lc.deck_id
JOIN users u ON u.id = lc.user_id
JOIN language_profiles lp ON lp.id = lc.profile_id
WHERE u.email = :email
  AND wl.deleted_at IS NULL
  AND wl.name IN :names
  AND lc.deleted_at IS NULL
  AND lc.enrichment_status = 'ready'
  AND lc.lexical_entry_id IS NULL
ON CONFLICT (lang_pair, lemma_l2, pos) DO NOTHING
RETURNING id
"""

ATTACH = """
UPDATE learning_cards lc
SET lexical_entry_id = le.id,
    updated_at = now()
FROM lexical_entries le, language_profiles lp, users u, word_lists wl
WHERE u.id = lc.user_id
  AND u.email = :email
  AND wl.id = lc.deck_id
  AND wl.deleted_at IS NULL
  AND wl.name IN :names
  AND lp.id = lc.profile_id
  AND lc.deleted_at IS NULL
  AND lc.lexical_entry_id IS NULL
  AND le.lang_pair = lp.app_lang || '>' || lp.learning_lang
  AND le.lemma_l2 = lc.lemma_l2
  AND le.pos IS NOT DISTINCT FROM lc.pos
RETURNING lc.id
"""

COUNTS = """
SELECT lc.enrichment_status, count(*)
FROM learning_cards lc
JOIN word_lists wl ON wl.id = lc.deck_id
JOIN users u ON u.id = lc.user_id
WHERE u.email = :email
  AND wl.deleted_at IS NULL
  AND wl.name IN :names
  AND lc.deleted_at IS NULL
GROUP BY lc.enrichment_status
ORDER BY 1
"""


async def main() -> None:
    from sqlalchemy import bindparam, text

    from app.db.session import async_session_factory

    params = {"email": EMAIL, "names": list(A2_NAMES)}

    def q(sql: str):
        return text(sql).bindparams(bindparam("names", expanding=True))

    async with async_session_factory() as db:
        async with db.begin():
            promoted = (await db.execute(q(PROMOTE), params)).rowcount
            cached = (await db.execute(q(CACHE_INSERT), params)).rowcount
            attached = (await db.execute(q(ATTACH), params)).rowcount
            rows = (await db.execute(q(COUNTS), params)).all()
        print(
            f"promoted={promoted} cache_insert={cached} attached={attached} totals={dict(rows)}",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
