"""Main's first request: lookup_draft on gpt-5.6-luna, no reasoning override."""
import asyncio
import json
import time

from app.ai.language_typology import lang_name_en, language_pair_guidance
from app.ai.prompts.v1 import LOOKUP_SYSTEM_V1
from app.services.llm import LLMService

USER = """Fast bilingual dictionary draft for ONE language pair.

{pair_guidance}

L1 (native): {native_name}
L2 (learning — every lemma MUST be in this language): {learning_name}
User query: "{text}"

Return up to 8 DISTINCT L2 headword proposals the user might mean.
Interpret generously: typos, missing diacritics, inflections, stray punctuation.
lemma = L2 citation form; gloss = L1 citation form.
pos = one of: noun, verb, adj, adv, prep, conj, pron, det, interj, phrase, construction, particle.
If the string is a word in BOTH languages, return both readings.
If several candidates share a gloss, add a short parenthetical.
JSON only:
{{
  "candidates": [
    {{"lemma": "...", "pos": "...", "gloss": "..."}}
  ]
}}
"""

CASES = [
    ("ser", "pl", "es"),
    ("droga", "pl", "es"),
    ("para", "pl", "es"),
    ("drogi", "pl", "es"),
    ("serr", "pl", "es"),
    ("ksiazka", "pl", "es"),
    ("Gift", "de", "en"),
    ("Haus", "de", "en"),
    ("chat", "fr", "en"),
    ("caht", "fr", "en"),
    ("red", "es", "en"),
    ("house", "en", "es"),
    ("casa", "pt", "en"),
]


async def one(llm: LLMService, text: str, native: str, learning: str) -> dict:
    prompt = USER.format(
        pair_guidance=language_pair_guidance(native=native, learning=learning),
        native_name=lang_name_en(native),
        learning_name=lang_name_en(learning),
        text=text,
    )
    t0 = time.perf_counter()
    resp = await llm.client.chat.completions.create(
        model="gpt-5.6-luna",
        messages=[
            {"role": "system", "content": LOOKUP_SYSTEM_V1},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=1200,
    )
    ms = round((time.perf_counter() - t0) * 1000)
    data = json.loads(resp.choices[0].message.content or "{}")
    rows = data.get("candidates") if isinstance(data, dict) else []
    return {"q": text, "pair": f"{native}-{learning}", "ms": ms, "rows": rows or []}


async def main() -> None:
    llm = LLMService()
    rows = await asyncio.gather(*(one(llm, *c) for c in CASES))
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    times = [r["ms"] for r in rows]
    print(json.dumps({"n": len(rows), "avg_ms": round(sum(times) / len(times)), "min_ms": min(times), "max_ms": max(times)}))


if __name__ == "__main__":
    asyncio.run(main())
