"""Summarize a few recently enriched production cards. No secrets."""
import asyncio
import json
from collections import Counter
from pathlib import Path

import asyncpg

dsn = ""
for line in Path(r"C:\Users\Usuario\Desktop\vocabulario\.env").read_text(encoding="utf-8").splitlines():
    if line.startswith("PROD_DATABASE_URL="):
        dsn = line.split("=", 1)[1].strip().strip('"').strip("'")
        break
dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")


def brief(content: dict) -> str:
    meanings = content.get("meanings") or []
    lines = []
    for index, meaning in enumerate(meanings, 1):
        examples = meaning.get("examples") or []
        levels = [ex.get("cefr") for ex in examples if isinstance(ex, dict)]
        lines.append(
            f"  sens {index}: {meaning.get('gloss_l1')} | "
            f"syn_l1={len(meaning.get('synonyms_l1') or [])} | "
            f"ex={levels} | usages={len(meaning.get('usages') or [])}"
        )
    assoc = content.get("associations_l2") or []
    pos = Counter((item.get("pos") if isinstance(item, dict) else "?") for item in assoc)
    family = content.get("word_family_l2") or []
    syn = content.get("synonyms_l2") or []
    ant = content.get("antonyms_l2") or []
    similar = content.get("similar_words") or []
    return (
        f"meanings={len(meanings)} ipa={bool(content.get('ipa'))} "
        f"syn_l2={len(syn)} ant_l2={len(ant)} family={len(family)} "
        f"assoc={len(assoc)} {dict(pos)} similar={len(similar)} "
        f"infl={bool(content.get('inflection') or content.get('conjugation'))}\n"
        + "\n".join(lines)
        + "\n  assoc: "
        + " | ".join(
            f"{item.get('lemma')}/{item.get('pos')}"
            for item in assoc
            if isinstance(item, dict)
        )
    )


async def main() -> None:
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT lemma_l2, pos, lemma_l1_primary, lang_pair, updated_at::date AS day,
                   content
            FROM lexical_entries
            WHERE updated_at > now() - interval '21 days'
              AND content->>'schema_version' = 'vocabulario.card.v1'
              AND jsonb_array_length(COALESCE(content->'meanings', '[]'::jsonb)) >= 1
              AND jsonb_array_length(COALESCE(content->'associations_l2', '[]'::jsonb)) >= 8
            ORDER BY updated_at DESC
            LIMIT 8
            """
        )
        print("n", len(rows))
        for row in rows:
            content = row["content"]
            if isinstance(content, str):
                content = json.loads(content)
            print(
                f"\n{row['day']} {row['lang_pair']} {row['lemma_l2']} ({row['pos']}) "
                f"= {row['lemma_l1_primary']}"
            )
            print(brief(content))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
