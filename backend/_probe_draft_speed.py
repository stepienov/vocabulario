"""Same main draft prompt, less thinking."""
import asyncio
import json
import time

from app.ai.language_typology import lang_name_en, language_pair_guidance
from app.ai.prompts.v1 import LOOKUP_SYSTEM_V1
from app.services.llm import LLMService
from _probe_main_draft import USER

CASES = [
    ("ser", "pl", "es"),
    ("droga", "pl", "es"),
    ("ksiazka", "pl", "es"),
    ("serr", "pl", "es"),
    ("drogi", "pl", "es"),
    ("Gift", "de", "en"),
    ("caht", "fr", "en"),
    ("red", "es", "en"),
]

CONFIGS = [
    ("56luna/none", "gpt-5.6-luna", "none"),
    ("56luna/low", "gpt-5.6-luna", "low"),
    ("6sol/none", "gpt-6-sol", "none"),
    ("6sol/low", "gpt-6-sol", "low"),
]


def brief(rows: list) -> list[str]:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(f"{row.get('lemma')}|{row.get('gloss')}|{row.get('pos')}")
    return out


async def one(llm: LLMService, cfg: tuple, text: str, native: str, learning: str) -> dict:
    label, model, effort = cfg
    prompt = USER.format(
        pair_guidance=language_pair_guidance(native=native, learning=learning),
        native_name=lang_name_en(native),
        learning_name=lang_name_en(learning),
        text=text,
    )
    t0 = time.perf_counter()
    resp = await llm.client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": LOOKUP_SYSTEM_V1},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=1200,
        reasoning_effort=effort,
        service_tier="priority",
    )
    ms = round((time.perf_counter() - t0) * 1000)
    data = json.loads(resp.choices[0].message.content or "{}")
    rows = data.get("candidates") if isinstance(data, dict) else []
    usage = getattr(resp, "usage", None)
    reasoning = getattr(usage, "completion_tokens_details", None)
    reasoning_tokens = getattr(reasoning, "reasoning_tokens", None) if reasoning else None
    return {
        "cfg": label,
        "q": text,
        "ms": ms,
        "reasoning_tokens": reasoning_tokens,
        "n": len(rows or []),
        "rows": brief(rows or []),
    }


async def main() -> None:
    llm = LLMService()
    rows = await asyncio.gather(*(one(llm, cfg, *case) for cfg in CONFIGS for case in CASES))
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    roll: dict[str, list[int]] = {}
    for row in rows:
        slot = roll.setdefault(row["cfg"], [0, 0])
        slot[0] += 1
        slot[1] += row["ms"]
    print(json.dumps({k: {"n": v[0], "avg_ms": round(v[1] / v[0])} for k, v in roll.items()}))


if __name__ == "__main__":
    asyncio.run(main())
