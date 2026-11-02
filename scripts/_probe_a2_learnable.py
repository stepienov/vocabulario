# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
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

SQL = """
SELECT wl.name, lc.lemma_l2, lc.pos,
       jsonb_array_length(COALESCE(lc.content->'similar_words', '[]'::jsonb)) AS similar_n,
       lc.content#>'{inflection,nouns,forms}' IS NOT NULL
           AND lc.content#>'{inflection,nouns,forms}' <> 'null'::jsonb AS has_noun_forms,
       lc.content#>'{inflection,adjectives,forms}' IS NOT NULL
           AND lc.content#>'{inflection,adjectives,forms}' <> 'null'::jsonb AS has_adj_forms,
       lc.content->'inflection' AS infl
FROM learning_cards lc
JOIN word_lists wl ON wl.id = lc.deck_id
JOIN users u ON u.id = lc.user_id
WHERE u.email = 'alextest@test.pl'
  AND wl.deleted_at IS NULL
  AND wl.name IN (
      'a2 1-10','a2 11-20','a2 21-30','a2 31-40',
      'a2 41-50','a2 51-60','a2 61-70','a2 71-80'
  )
  AND lc.deleted_at IS NULL
  AND lc.enrichment_status = 'learnable'
ORDER BY wl.name, lc.lemma_l2
"""


async def main() -> None:
    from sqlalchemy import text

    from app.db.session import async_session_factory

    async with async_session_factory() as db:
        rows = (await db.execute(text(SQL))).mappings().all()
    print(f"n={len(rows)}", flush=True)
    for r in rows:
        print(
            f"{r['name']:12s} {r['lemma_l2']!r:30s} pos={r['pos']!r:10s} "
            f"sim={r['similar_n']} noun={r['has_noun_forms']} adj={r['has_adj_forms']} "
            f"infl={json.dumps(r['infl'], ensure_ascii=False)[:160]}",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
