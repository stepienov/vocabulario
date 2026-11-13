"""Run main's lookup-expand prompt on the same loose cases."""
import asyncio
import json
import time

from app.ai.language_typology import lang_name_en, language_pair_guidance
from app.ai.prompts.v1 import LOOKUP_EXPAND_PROMPT_V1, LOOKUP_SYSTEM_V1, lookup_output_form_rules_text
from app.services.llm import LLMService
from _probe_expand import CASES, bag, judge

CONFIGS = [
    ("6sol/none", "gpt-6-sol", "none"),
    ("terra/none", "gpt-5.6-terra", "none"),
]


def already_block(case) -> str:
    if not case.already:
        return (
            "None yet — this is a cold start. Return the full high-recall "
            "union of all plausible readings (up to 16)."
        )
    lines = ["Already stored (do NOT repeat these lemma+pos pairs):"]
    for word, translation in case.already:
        lines.append(f"- lemma={word}; pos=noun; gloss={translation}")
    return "\n".join(lines)


def prompt_for(case) -> str:
    native = {"polski": "pl", "francuski": "fr", "niemiecki": "de", "hiszpański": "es"}[case.language_1]
    learning = {"hiszpański": "es", "angielski": "en"}[case.language_2]
    return LOOKUP_EXPAND_PROMPT_V1.format(
        pair_guidance=language_pair_guidance(native=native, learning=learning),
        native_name=lang_name_en(native),
        learning_name=lang_name_en(learning),
        cefr="A2",
        text=case.query,
        already_block=already_block(case),
        lookup_output_form_rules=lookup_output_form_rules_text(native, learning),
    )


def as_pairs(rows: list[dict]) -> list[dict]:
    return [
        {"word": row.get("lemma"), "translation": row.get("gloss"), "pos": row.get("pos")}
        for row in rows
        if isinstance(row, dict)
    ]


async def call(llm: LLMService, cfg: tuple, case) -> dict:
    label, model, effort = cfg
    t0 = time.perf_counter()
    resp = await llm.client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": LOOKUP_SYSTEM_V1},
            {"role": "user", "content": prompt_for(case)},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=700,
        reasoning_effort=effort,
        service_tier="priority",
    )
    ms = round((time.perf_counter() - t0) * 1000)
    data = json.loads(resp.choices[0].message.content or "{}")
    rows = as_pairs(data.get("candidates") or [])
    problems = judge(case, rows)
    return {"ok": not problems, "cfg": label, "q": case.query, "ms": ms, "problems": problems, "pairs": rows}


async def main() -> None:
    llm = LLMService()
    rows = await asyncio.gather(*(call(llm, cfg, case) for cfg in CONFIGS for case in CASES))
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    roll: dict[str, list[int]] = {}
    for row in rows:
        slot = roll.setdefault(row["cfg"], [0, 0, 0])
        slot[1] += 1
        slot[0] += int(row["ok"])
        slot[2] += row["ms"]
    print(json.dumps({k: {"passed": v[0], "total": v[1], "avg_ms": round(v[2] / v[1])} for k, v in roll.items()}))


if __name__ == "__main__":
    asyncio.run(main())
