"""Porównanie 1 vs 3 wywołań LLM przy generowaniu odmiany (test koszt/jakość)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Windows: konsola często cp1250 — unikaj UnicodeEncodeError przy arabskim itd.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from openai import AsyncOpenAI  # noqa: E402

from app.ai.prompts.v1 import build_conjugation_prompt  # noqa: E402
from app.core.config import get_settings  # noqa: E402

# 3 słowa w 3 z 5 języków (limit tokenów) — reprezentatywne typy morfologii
CASES = [
    ("pl", "rzucić"),
    ("es", "hablar"),
    ("ar", "كتب"),
]

SPLIT_GROUPS = [
    ("finite_main", "Generate ONLY these finite tenses as JSON tenses object: present/main tense set for this language."),
    ("finite_secondary", "Generate ONLY remaining finite tenses (past, future, subjunctive, etc.) as JSON tenses object."),
    ("non_finite", "Generate ONLY non_finite forms and periphrases array. tenses must be empty object."),
]


async def call_json(client: AsyncOpenAI, model: str, prompt: str) -> tuple[dict, int, int]:
    kwargs: dict = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Return only valid JSON for conjugation/inflection. No markdown.",
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    if not model.lower().startswith(("gpt-5", "o1", "o3", "o4")):
        kwargs["temperature"] = 0.2
    resp = await client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or "{}"
    usage = resp.usage
    return json.loads(text), usage.prompt_tokens or 0, usage.completion_tokens or 0


def count_forms(data: dict) -> int:
    n = 0
    tenses = data.get("tenses") or {}
    if isinstance(tenses, dict):
        for forms in tenses.values():
            if isinstance(forms, dict):
                n += sum(1 for v in forms.values() if v and str(v).strip() not in {"—", "-", "n/a"})
    nf = data.get("non_finite") or {}
    if isinstance(nf, dict):
        n += sum(1 for v in nf.values() if v and str(v).strip() not in {"—", "-", "n/a"})
    per = data.get("periphrases") or []
    if isinstance(per, list):
        n += len(per)
    return n


async def run_one(lang: str, lemma: str, client: AsyncOpenAI, model: str) -> dict:
    base = build_conjugation_prompt(
        lemma=lemma,
        learning=lang,
        native="pl",
    )

    unified, u_in, u_out = await call_json(client, model, base)
    unified_forms = count_forms(unified)

    split_parts: list[dict] = []
    total_in = total_out = 0
    merged: dict = {"tenses": {}, "non_finite": {}, "periphrases": [], "ui_meta": {}}
    for _name, extra in SPLIT_GROUPS:
        p = base + f"\n\nSPLIT MODE: {extra}"
        part, i, o = await call_json(client, model, p)
        total_in += i
        total_out += o
        if part.get("ui_meta"):
            merged["ui_meta"] = part["ui_meta"]
        t = part.get("tenses") or {}
        if isinstance(t, dict):
            merged["tenses"].update(t)
        nf = part.get("non_finite") or {}
        if isinstance(nf, dict):
            merged["non_finite"].update(nf)
        per = part.get("periphrases") or []
        if isinstance(per, list):
            merged["periphrases"].extend(per)
        split_parts.append(part)

    split_forms = count_forms(merged)

    return {
        "lang": lang,
        "lemma": lemma,
        "unified": {
            "forms": unified_forms,
            "prompt_tokens": u_in,
            "completion_tokens": u_out,
            "tense_keys": list((unified.get("tenses") or {}).keys()),
        },
        "split_x3": {
            "forms": split_forms,
            "prompt_tokens": total_in,
            "completion_tokens": total_out,
            "tense_keys": list((merged.get("tenses") or {}).keys()),
        },
    }


async def main() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        print("Brak OPENAI_API_KEY")
        sys.exit(1)
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    model = settings.llm_enrichment_model
    results = []
    for lang, lemma in CASES:
        print(f"Testing {lang} / {lemma}...", flush=True)
        results.append(await run_one(lang, lemma, client, model))

    print("\n=== WYNIKI ===")
    total_u_in = total_u_out = total_s_in = total_s_out = 0
    for r in results:
        u, s = r["unified"], r["split_x3"]
        total_u_in += u["prompt_tokens"]
        total_u_out += u["completion_tokens"]
        total_s_in += s["prompt_tokens"]
        total_s_out += s["completion_tokens"]
        print(
            f"{r['lang']:>3} {r['lemma']:<8} | "
            f"1× forms={u['forms']:>3} tok={u['prompt_tokens']+u['completion_tokens']:>5} | "
            f"3× forms={s['forms']:>3} tok={s['prompt_tokens']+s['completion_tokens']:>5} | "
            f"tenses 1×={len(u['tense_keys'])} 3×={len(s['tense_keys'])}"
        )
    print(
        f"\nSUMA tokenów: 1×={total_u_in+total_u_out}  3×={total_s_in+total_s_out}  "
        f"różnica={total_s_in+total_s_out - (total_u_in+total_u_out):+d}"
    )
    out = ROOT / "docs" / "inflection-shot-test-results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Zapisano: {out}")


if __name__ == "__main__":
    asyncio.run(main())
