"""Short enrich-core probe. One compact prompt, reasoning off."""
import asyncio
import json
import time
from collections import Counter
from pathlib import Path

from openai import AsyncOpenAI

key = ""
for line in Path(r"C:\Users\Usuario\Desktop\vocabulario\.env").read_text(encoding="utf-8").splitlines():
    if line.startswith("OPENAI_API_KEY="):
        key = line.split("=", 1)[1].strip().strip('"').strip("'")
        break
client = AsyncOpenAI(api_key=key)

SYSTEM = """You write one learner flashcard core for a single dictionary headword. JSON only.
lemma is the same L2 headword. A Spanish noun is written with its dictionary article even when the input omitted it: frontera becomes la frontera. Do not translate the lemma into L1.
gloss_l1 and example l1 are L1. Example l2, synonyms_l2, antonyms_l2, word_family_l2 and associations_l2 lemmas are L2.
Meanings in frequency order. Each meaning has exactly 3 full sentences: A2 short, B2 complex, C2 idiomatic. No repeated l2 sentence.
synonyms_l2 and antonyms_l2 match the headword POS. word_family_l2 is same-root derivation only, other POS allowed, never the headword, never a negative prefix.
associations_l2 is one everyday scene, 16 to 18 items, other roots: about half nouns, at least 4 verbs, at least 3 adjectives, one adverb if it fits. Not synonyms and not the word family.
For a Spanish noun, lemma includes the dictionary article el, la, los or las.
ipa transcribes the word itself, without the article. No conjugation table. No similar_words."""

USER = """L1: {l1}. L2: {l2}. CEFR: B1.
Lemma: {lemma}
POS: {pos}
Gloss hint: {gloss}
Return this JSON shape:
{{
  "lemma": "{lemma}",
  "pos": "{pos}",
  "ipa": "...",
  "meanings": [
    {{
      "gloss_l1": "...",
      "synonyms_l1": ["..."],
      "examples": [
        {{"l2": "...", "l1": "...", "cefr": "A2"}},
        {{"l2": "...", "l1": "...", "cefr": "B2"}},
        {{"l2": "...", "l1": "...", "cefr": "C2"}}
      ],
      "usages": [{{"l2": "...", "l1": "..."}}]
    }}
  ],
  "synonyms_l2": [{{"lemma": "...", "pos": "{pos}", "gloss_l1": "..."}}],
  "antonyms_l2": [{{"lemma": "...", "pos": "{pos}", "gloss_l1": "..."}}],
  "word_family_l2": [{{"lemma": "...", "pos": "...", "gloss_l1": "..."}}],
  "associations_l2": [{{"lemma": "...", "pos": "noun|verb|adj|adv", "gloss_l1": "..."}}]
}}"""

CASES = [
    ("frontera", "noun", "granica"),
]


def summarize(data: dict) -> str:
    meanings = data.get("meanings") or []
    bits = []
    for index, meaning in enumerate(meanings, 1):
        if not isinstance(meaning, dict):
            continue
        levels = []
        samples = []
        for ex in meaning.get("examples") or []:
            if not isinstance(ex, dict):
                continue
            levels.append(ex.get("cefr"))
            samples.append(f"{ex.get('cefr')}:{ex.get('l2')}")
        bits.append(
            f"sens{index}={meaning.get('gloss_l1')} usages={len(meaning.get('usages') or [])}\n    "
            + "\n    ".join(samples)
        )
    assoc = [a for a in (data.get("associations_l2") or []) if isinstance(a, dict)]
    pos = Counter(str(a.get("pos")) for a in assoc)
    family = [a.get("lemma") for a in (data.get("word_family_l2") or []) if isinstance(a, dict)]
    syn = [a.get("lemma") for a in (data.get("synonyms_l2") or []) if isinstance(a, dict)]
    return (
        f"ipa={data.get('ipa')!r} lemma={data.get('lemma')!r} meanings={len(meanings)} "
        f"syn={syn} family={family} assoc={len(assoc)} {dict(pos)}\n  "
        + "\n  ".join(bits)
    )


async def one(case: tuple[str, str, str]) -> None:
    lemma, pos, gloss = case
    t0 = time.perf_counter()
    resp = await client.chat.completions.create(
        model="gpt-5.6-terra",
        messages=[
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": USER.format(
                    l1="Polish", l2="Spanish", lemma=lemma, pos=pos, gloss=gloss
                ),
            },
        ],
        max_completion_tokens=4500,
        reasoning_effort="none",
        response_format={"type": "json_object"},
    )
    ms = int((time.perf_counter() - t0) * 1000)
    usage = resp.usage
    details = getattr(usage, "completion_tokens_details", None)
    reason = getattr(details, "reasoning_tokens", None) if details else None
    raw = resp.choices[0].message.content or ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    print(
        f"\n{lemma} {ms}ms in={usage.prompt_tokens if usage else None} "
        f"out={usage.completion_tokens if usage else None} reason={reason or 0} "
        f"finish={resp.choices[0].finish_reason}"
    )
    print(summarize(data))


async def main() -> None:
    await asyncio.gather(*(one(case) for case in CASES))


if __name__ == "__main__":
    asyncio.run(main())
