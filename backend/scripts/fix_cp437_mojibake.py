"""Fix text corrupted by UTF-8 bytes misread as CP852 (Windows OEM), then stored as UTF-8."""
from __future__ import annotations

import asyncio
import json
import sys

import asyncpg

CHARS = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻáéíóúñüÁÉÍÓÚÑÜ¿¡"


def corrupted(ch: str) -> str:
    return ch.encode("utf-8").decode("cp852")


def _cp852_reverse_map() -> dict[str, int]:
    return {bytes([b]).decode("cp852"): b for b in range(256)}


def is_box(ch: str) -> bool:
    return 0x2500 <= ord(ch) <= 0x257F


def fix_box_sequences(text: str, rev: dict[str, int]) -> str:
    """Reverse CP852 mojibake starting at box-drawing lead chars (safe for already-fixed Polish)."""
    if not any(is_box(ch) for ch in text):
        return text

    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if is_box(text[i]) and text[i] in rev:
            matched = False
            for length in (3, 2):
                if i + length > n:
                    continue
                chunk = text[i : i + length]
                if not all(ch in rev for ch in chunk):
                    continue
                buf = bytes(rev[ch] for ch in chunk)
                lead = buf[0]
                if length == 2 and not (0xC2 <= lead <= 0xDF):
                    continue
                if length == 3 and not (0xE0 <= lead <= 0xEF):
                    continue
                try:
                    decoded = buf.decode("utf-8")
                except UnicodeDecodeError:
                    continue
                out.append(decoded)
                i += length
                matched = True
                break
            if matched:
                continue
        out.append(text[i])
        i += 1
    return "".join(out)


async def main() -> None:
    deduped: dict[str, str] = {}
    for ch in CHARS:
        deduped.setdefault(corrupted(ch), ch)

    rev = _cp852_reverse_map()
    conn = await asyncpg.connect(
        "postgresql://vocabulario:vocabulario_dev@127.0.0.1:5432/vocabulario"
    )
    try:
        text_fixes = [
            ("word_lists", "name"),
            ("learning_cards", "gloss_primary"),
            ("learning_cards", "lemma_l2"),
            ("learning_cards", "enrichment_error"),
            ("lexical_entries", "lemma_l2"),
            ("lexical_entries", "lemma_l1_primary"),
            ("lexical_entries", "pos"),
        ]
        for table, col in text_fixes:
            total = 0
            for bad, good in deduped.items():
                result = await conn.execute(
                    f"UPDATE {table} SET {col} = replace({col}, $1, $2) "
                    f"WHERE {col} LIKE '%' || $1 || '%'",
                    bad,
                    good,
                )
                total += int(result.split()[-1])
            print(f"replace {table}.{col}: {total}")

        for table in ("lexical_entries", "learning_cards"):
            total = 0
            for bad, good in deduped.items():
                result = await conn.execute(
                    f"UPDATE {table} SET content = replace(content::text, $1, $2)::jsonb "
                    f"WHERE content::text LIKE '%' || $1 || '%'",
                    bad,
                    good,
                )
                total += int(result.split()[-1])
            print(f"replace {table}.content: {total}")

        # Second pass: IPA / leftover box-drawing sequences
        for table in ("lexical_entries", "learning_cards"):
            rows = await conn.fetch(
                f"SELECT id, content FROM {table} WHERE content::text ~ '[\u2500-\u257F]'"
            )
            fixed_n = 0
            for row in rows:
                raw = (
                    row["content"]
                    if isinstance(row["content"], str)
                    else json.dumps(row["content"], ensure_ascii=False)
                )
                fixed = fix_box_sequences(raw, rev)
                if fixed != raw:
                    await conn.execute(
                        f"UPDATE {table} SET content = $1::jsonb WHERE id = $2",
                        fixed,
                        row["id"],
                    )
                    fixed_n += 1
            print(f"box-fix {table}.content: {fixed_n}/{len(rows)}")

        for table, col in text_fixes:
            rows = await conn.fetch(
                f"SELECT id, {col} AS val FROM {table} "
                f"WHERE {col} IS NOT NULL AND {col} ~ '[\u2500-\u257F]'"
            )
            fixed_n = 0
            for row in rows:
                fixed = fix_box_sequences(row["val"], rev)
                if fixed != row["val"]:
                    await conn.execute(
                        f"UPDATE {table} SET {col} = $1 WHERE id = $2",
                        fixed,
                        row["id"],
                    )
                    fixed_n += 1
            if rows:
                print(f"box-fix {table}.{col}: {fixed_n}/{len(rows)}")

        remaining = await conn.fetchval(
            """
            SELECT count(*) FROM (
              SELECT 1 FROM lexical_entries WHERE content::text ~ '[\u2500-\u257F]'
              UNION ALL
              SELECT 1 FROM learning_cards WHERE content::text ~ '[\u2500-\u257F]'
              UNION ALL
              SELECT 1 FROM word_lists WHERE name ~ '[\u2500-\u257F]'
            ) t
            """
        )
        print(f"rows_still_with_box_drawing: {remaining}")

        row = await conn.fetchrow(
            "SELECT lemma_l2, lemma_l1_primary, content FROM lexical_entries "
            "WHERE lemma_l2 = 'dejar'"
        )
        if row:
            print(f"{row['lemma_l2']} -> {row['lemma_l1_primary']}")
            print(f"ipa: {row['content'].get('ipa')}")
            text = json.dumps(row["content"], ensure_ascii=False)
            print("box?", any(is_box(ch) for ch in text))

        lists = await conn.fetch("SELECT name FROM word_lists WHERE is_system")
        for item in lists:
            print(f"list: {item['name']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main())
