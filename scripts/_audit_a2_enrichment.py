# -*- coding: utf-8 -*-
"""Read-only audit: czy karty A2 mają pełny enrichment."""
from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter, defaultdict
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

SQL = """
SELECT wl.name AS list_name, lc.lemma_l2, lc.pos, lc.enrichment_status,
       lc.lexical_entry_id IS NOT NULL AS has_cache,
       lc.content, lp.learning_lang
FROM learning_cards lc
JOIN word_lists wl ON wl.id = lc.deck_id
JOIN users u ON u.id = lc.user_id
JOIN language_profiles lp ON lp.id = lc.profile_id
WHERE u.email = :email
  AND wl.deleted_at IS NULL
  AND wl.name IN :names
  AND lc.deleted_at IS NULL
ORDER BY wl.name, lc.lemma_l2
"""


def _items(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict)]


def _example_cefrs(meanings: list[dict]) -> set[str]:
    out: set[str] = set()
    for m in meanings:
        for ex in m.get("examples") or []:
            if isinstance(ex, dict) and ex.get("cefr"):
                out.add(str(ex["cefr"]).upper())
    return out


def _example_stats(meanings: list[dict]) -> tuple[int, int, int]:
    """meanings, examples with l2+l1, examples missing translation."""
    n_mean = len(meanings)
    ok = 0
    bad = 0
    for m in meanings:
        for ex in m.get("examples") or []:
            if not isinstance(ex, dict):
                bad += 1
                continue
            if (ex.get("l2") or "").strip() and (ex.get("l1") or "").strip():
                ok += 1
            else:
                bad += 1
    return n_mean, ok, bad


async def main() -> None:
    from sqlalchemy import bindparam, text

    from app.ai.schemas.similar_words import MIN_SIMILAR_FOR_QUIZ, MIN_SIMILAR_WORDS
    from app.db.session import async_session_factory
    from app.services.card_jobs import content_is_complete, inflect_pos_key
    from app.services.distractors import quiz_pos_matches

    q = text(SQL).bindparams(bindparam("names", expanding=True))
    async with async_session_factory() as db:
        rows = (await db.execute(q, {"email": EMAIL, "names": list(A2_NAMES)})).mappings().all()

    status = Counter()
    pos_n = Counter()
    list_n = Counter()
    fails: dict[str, list[str]] = defaultdict(list)
    similar_counts: list[int] = []
    syn_counts: list[int] = []
    ant_counts: list[int] = []
    fam_counts: list[int] = []
    assoc_counts: list[int] = []
    ex_counts: list[int] = []
    ipa_ok = 0
    cache_ok = 0
    complete_ok = 0
    quiz_ok = 0
    cefr_full = 0  # has A2+B2+C2

    for r in rows:
        lemma = r["lemma_l2"]
        pos = r["pos"] or ""
        content = r["content"] or {}
        tag = f"{r['list_name']} | {lemma} ({pos})"
        status[r["enrichment_status"]] += 1
        pos_n[pos] += 1
        list_n[r["list_name"]] += 1
        if r["has_cache"]:
            cache_ok += 1
        if r["enrichment_status"] != "ready":
            fails["not_ready"].append(tag)

        complete = content_is_complete(content, learning_lang=r["learning_lang"])
        if complete:
            complete_ok += 1
        else:
            fails["not_complete"].append(tag)

        similar = _items(content.get("similar_words"))
        similar_n = len(similar)
        similar_counts.append(similar_n)
        if similar_n < MIN_SIMILAR_WORDS:
            fails["similar_lt_12"].append(f"{tag} n={similar_n}")
        if similar_n < MIN_SIMILAR_FOR_QUIZ:
            fails["similar_lt_7"].append(f"{tag} n={similar_n}")

        lemmas = [(s.get("lemma") or "").strip() for s in similar]
        glossed = [s for s in similar if (s.get("lemma") or "").strip() and (s.get("gloss_l1") or "").strip()]
        unique = {x.lower() for x in lemmas if x}
        if len(unique) < similar_n:
            fails["similar_dupes"].append(f"{tag} unique={len(unique)}/{similar_n}")
        if lemma.lower() in unique:
            fails["similar_includes_self"].append(tag)
        missing_gloss = similar_n - len(glossed)
        if missing_gloss:
            fails["similar_no_gloss"].append(f"{tag} missing={missing_gloss}")

        exact = [
            s
            for s in similar
            if (s.get("lemma") or "").lower() != lemma.lower()
            and quiz_pos_matches(pos, s.get("pos"), family=False)
        ]
        exact_unique = {(s.get("lemma") or "").strip().lower() for s in exact if s.get("lemma")}
        if len(exact_unique) >= MIN_SIMILAR_FOR_QUIZ:
            quiz_ok += 1
        else:
            fails["quiz_lt_7_same_pos"].append(
                f"{tag} exact_pos={len(exact_unique)} similar={similar_n}"
            )

        meanings = [m for m in (content.get("meanings") or []) if isinstance(m, dict)]
        n_mean, ex_ok, ex_bad = _example_stats(meanings)
        ex_counts.append(ex_ok)
        if n_mean < 1:
            fails["no_meanings"].append(tag)
        if ex_ok < 3:
            fails["examples_lt_3"].append(f"{tag} ex={ex_ok} meanings={n_mean}")
        if ex_bad:
            fails["broken_examples"].append(f"{tag} bad={ex_bad}")
        cefrs = _example_cefrs(meanings)
        if {"A2", "B2", "C2"} <= cefrs:
            cefr_full += 1
        else:
            fails["examples_missing_cefr_band"].append(f"{tag} cefr={sorted(cefrs)}")

        if (content.get("ipa") or "").strip():
            ipa_ok += 1
        else:
            fails["no_ipa"].append(tag)

        syn = _items(content.get("synonyms_l2"))
        ant = _items(content.get("antonyms_l2"))
        fam = _items(content.get("word_family_l2"))
        assoc = _items(content.get("associations_l2"))
        syn_counts.append(len(syn))
        ant_counts.append(len(ant))
        fam_counts.append(len(fam))
        assoc_counts.append(len(assoc))
        if not syn:
            fails["no_synonyms"].append(tag)
        if not ant:
            fails["no_antonyms"].append(tag)
        if not fam:
            fails["no_family"].append(tag)

        key = inflect_pos_key(pos, lemma=lemma, learning_lang=r["learning_lang"])
        inf = content.get("inflection") if isinstance(content.get("inflection"), dict) else {}
        if key == "verb":
            verbs = inf.get("verbs") if isinstance(inf, dict) else None
            has = isinstance(verbs, dict) and (verbs.get("tenses") or verbs.get("non_finite"))
            has = has or bool(content.get("conjugation"))
            if not has:
                fails["no_verb_infl"].append(tag)
        elif key == "noun":
            if not (isinstance(inf.get("nouns"), dict) and inf.get("nouns")):
                fails["no_noun_infl"].append(tag)
        elif key == "adj":
            if not (isinstance(inf.get("adjectives"), dict) and inf.get("adjectives")):
                fails["no_adj_infl"].append(tag)

    def dist(xs: list[int]) -> str:
        if not xs:
            return "n/a"
        c = Counter(xs)
        return (
            f"min={min(xs)} p50={sorted(xs)[len(xs)//2]} max={max(xs)} "
            f"zero={sum(1 for x in xs if x == 0)} hist={dict(sorted(c.items()))}"
        )

    n = len(rows)
    print(f"cards={n} lists={dict(list_n)} pos={dict(pos_n)} status={dict(status)}", flush=True)
    print(f"ready={status.get('ready', 0)}/{n}", flush=True)
    print(f"content_is_complete={complete_ok}/{n}", flush=True)
    print(f"lexical_cache={cache_ok}/{n}", flush=True)
    print(f"ipa={ipa_ok}/{n}", flush=True)
    print(f"examples_A2+B2+C2={cefr_full}/{n}", flush=True)
    print(f"quiz_7_same_pos_similar={quiz_ok}/{n} (need {MIN_SIMILAR_FOR_QUIZ}, target {MIN_SIMILAR_WORDS})", flush=True)
    print(f"similar_words {dist(similar_counts)}", flush=True)
    print(f"examples_ok {dist(ex_counts)}", flush=True)
    print(f"synonyms_l2 {dist(syn_counts)}", flush=True)
    print(f"antonyms_l2 {dist(ant_counts)}", flush=True)
    print(f"word_family_l2 {dist(fam_counts)}", flush=True)
    print(f"associations_l2 {dist(assoc_counts)}", flush=True)
    print("--- issues ---", flush=True)
    for k, items in sorted(fails.items()):
        print(f"{k}: {len(items)}", flush=True)
        for line in items[:12]:
            print(f"  {line}", flush=True)
        if len(items) > 12:
            print(f"  … +{len(items) - 12}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
