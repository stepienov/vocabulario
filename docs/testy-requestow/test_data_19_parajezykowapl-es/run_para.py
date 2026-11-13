"""Pierwsza para: polski i hiszpański. Prawdziwe wyszukiwanie, bez drugiej pary."""
import asyncio
import json
import sys
import unicodedata
from datetime import UTC, datetime

from sqlalchemy import select, text

from app.db.session import async_session_factory
from app.models import LanguageProfile, User
from app.services.lexical import LexicalService
from app.services.lookup_candidates import normalize_lookup_query
from app.services.pos_normalize import lemma_stem, normalize_pos_bucket

OUT = sys.argv[1]
QUERIES = [
    "droga",
    "drogas",
    "drogie",
    "drogie3",
    "drog",
    "somos",
    "para",
    "cara",
    "casa",
    "wdoa",
    "idę",
    "trasa",
]


def fold(value: str) -> str:
    text_value = unicodedata.normalize("NFD", (value or "").casefold())
    text_value = "".join(ch for ch in text_value if unicodedata.category(ch) != "Mn")
    return text_value.replace("ł", "l")


def tokens(value: str) -> set[str]:
    raw = (value or "").replace("/", " ").replace(",", " ").replace(";", " ")
    return {fold(part) for part in raw.split() if part}


def row_text(rows: list[dict]) -> str:
    parts = []
    for row in rows:
        parts.append(
            f"{row.get('lemma')}/{normalize_pos_bucket(row.get('pos'))}/{row.get('gloss')}"
        )
    return " | ".join(parts) or "(pusto)"


def has_any(rows: list[dict], words: set[str]) -> bool:
    for row in rows:
        bag = tokens(row.get("lemma") or "") | tokens(row.get("gloss") or "")
        stem = fold(lemma_stem(row.get("lemma") or "", "es"))
        bag.add(stem)
        if bag & words:
            return True
    return False


def noun_articles(rows: list[dict]) -> list[str]:
    bad = []
    for row in rows:
        if normalize_pos_bucket(row.get("pos")) != "noun":
            continue
        lemma = (row.get("lemma") or "").strip()
        first = lemma.split()[0].casefold() if lemma else ""
        if first not in {"el", "la", "los", "las"}:
            bad.append(lemma)
    return bad


def feminine_adjective(rows: list[dict]) -> list[str]:
    bad = []
    for row in rows:
        if normalize_pos_bucket(row.get("pos")) != "adj":
            continue
        stem = fold(lemma_stem(row.get("lemma") or "", "es"))
        if stem in {"cara", "bonita", "querida", "costosa"}:
            bad.append(row.get("lemma") or "")
    return bad


def polish_headword(rows: list[dict]) -> list[str]:
    bad = []
    for row in rows:
        lemma = row.get("lemma") or ""
        if any(ch in lemma.casefold() for ch in "ąćęłńóśźż"):
            bad.append(lemma)
        stem = fold(lemma_stem(lemma, "es"))
        if stem in {"trasa", "kasa", "kara", "drogi", "droga"} and not lemma.split()[:1]:
            continue
        if stem == "trasa":
            bad.append(lemma)
    return bad


def judge(query: str, rows: list[dict]) -> list[str]:
    problems = []
    road = has_any(rows, {"camino", "carretera", "via", "calle"})
    drug = has_any(rows, {"narkotyk", "droga"}) and has_any(rows, {"droga", "narkotyk"})
    # drug: gloss narkotyk, or lemma la droga. Avoid counting Polish gloss "droga" on camino as the drug.
    drug = any(
        "narkotyk" in tokens(row.get("gloss") or "")
        or fold(lemma_stem(row.get("lemma") or "", "es")) == "droga"
        for row in rows
    )
    pricey = has_any(rows, {"caro", "costoso", "querido", "drogi"})
    water = has_any(rows, {"agua", "woda"})
    to_be = any(
        normalize_pos_bucket(row.get("pos")) == "verb"
        and fold(lemma_stem(row.get("lemma") or "", "es")) == "ser"
        and "byc" in tokens(row.get("gloss") or "")
        for row in rows
    )
    pair_noun = has_any(rows, {"par"})
    for_prep = has_any(rows, {"dla"})
    face = has_any(rows, {"twarz", "rostro", "cara"})
    punishment = has_any(rows, {"kara", "castigo", "pena"})
    house = has_any(rows, {"casa", "dom"})
    checkout = any("kasa" in tokens(row.get("gloss") or "") for row in rows)
    go = any(
        fold(lemma_stem(row.get("lemma") or "", "es")) in {"ir", "irse"}
        and "isc" in tokens(row.get("gloss") or "") or "chodzic" in tokens(row.get("gloss") or "")
        for row in rows
    )
    go = any(
        fold(lemma_stem(row.get("lemma") or "", "es")) in {"ir", "irse"}
        for row in rows
    ) and has_any(rows, {"isc", "chodzic"})
    route = has_any(rows, {"ruta", "recorrido", "trayecto", "trasa"})

    need = {
        "droga": [("droga", road), ("narkotyk", drug), ("drogi", pricey)],
        "drogas": [("droga", road), ("narkotyk", drug)],
        "drogie": [("drogi", pricey)],
        "drogie3": [("drogi", pricey)],
        "drog": [("droga", road), ("narkotyk", drug), ("drogi", pricey)],
        "somos": [("być", to_be), ("ser", to_be)],
        "para": [("para", pair_noun), ("dla", for_prep)],
        "cara": [("twarz", face), ("drogi", pricey), ("kara", punishment)],
        "casa": [("dom", house), ("kasa", checkout)],
        "wdoa": [("woda", water)],
        "idę": [("iść", go)],
        "trasa": [("trasa", route)],
    }
    forbid = {
        "drogie": [("droga", road), ("narkotyk", drug)],
        "drogie3": [("droga", road), ("narkotyk", drug)],
        "wdoa": [("droga", road), ("narkotyk", drug)],
    }
    for name, ok in need[query]:
        if not ok:
            problems.append(f"brak:{name}")
    for name, ok in forbid.get(query, []):
        if ok:
            problems.append(f"za-daleko:{name}")
    if query in {"drogas", "cara", "casa", "trasa", "droga", "drog", "wdoa"}:
        for lemma in noun_articles(rows):
            problems.append(f"rzeczownik-bez-rodzajnika:{lemma}")
    if query == "cara":
        for lemma in feminine_adjective(rows):
            problems.append(f"przymiotnik-zenski:{lemma}")
    if query == "trasa":
        for lemma in polish_headword(rows):
            problems.append(f"haslo-polskie:{lemma}")
    if query == "idę":
        for row in rows:
            stem = fold(lemma_stem(row.get("lemma") or "", "es"))
            gloss = fold(row.get("gloss") or "")
            if stem in {"voy", "ide"} or gloss in {"ide", "voy"}:
                problems.append(f"forma-osobowa:{row.get('lemma')}/{row.get('gloss')}")
    return problems


async def calls_since(db, query: str, start: datetime) -> int:
    value = (
        await db.execute(
            text(
                """
                select count(*) from llm_usage
                where query = :q and created_at >= :start
                  and purpose in ('lookup_draft', 'lookup_expand')
                """
            ),
            {"q": query, "start": start},
        )
    ).scalar()
    return int(value or 0)


async def main():
    start = datetime.now(UTC)
    async with async_session_factory() as db:
        profile = (
            await db.execute(
                select(LanguageProfile).where(
                    LanguageProfile.app_lang == "pl",
                    LanguageProfile.learning_lang == "es",
                )
            )
        ).scalars().first()
        if profile is None:
            raise SystemExit("brak profilu pl>es")
        user = (
            await db.execute(select(User).where(User.id == profile.user_id))
        ).scalar_one()
        keys = sorted({normalize_lookup_query(q) for q in QUERIES})
        await db.execute(
            text(
                "delete from lookup_query_cache where lang_pair = 'pl>es' and input_norm = any(:k)"
            ),
            {"k": keys},
        )
        await db.commit()
        db.expunge(user)
        profile_id = profile.id

    lines = [f"start {start.isoformat()} profile {profile_id}"]
    async with async_session_factory() as db:
        service = LexicalService(db)
        for query in QUERIES:
            before = datetime.now(UTC)
            outcome = await service.lookup_cached(user, profile_id, query, annotate=False)
            await db.commit()
            await asyncio.sleep(1.0)
            used = await calls_since(db, query, before)
            rows = [dict(c) for c in outcome.candidates]
            problems = judge(query, rows)
            mark = "ok  " if not problems else "FAIL"
            lines.append(
                f"{mark} {query} calls={used} source={outcome.source} exhausted={outcome.suggestions_exhausted}"
            )
            lines.append(f"     {row_text(rows)}")
            for problem in problems:
                lines.append(f"     -> {problem}")

        # trasa: cache i dociąganie, od czystego zapisu
        await db.execute(
            text(
                "delete from lookup_query_cache where lang_pair = 'pl>es' and input_norm = :k"
            ),
            {"k": normalize_lookup_query("trasa")},
        )
        await db.commit()
        lines.append("--- trasa cache ---")
        t0 = datetime.now(UTC)
        first = await service.lookup_cached(user, profile_id, "trasa", annotate=False)
        await db.commit()
        await asyncio.sleep(1.0)
        c1 = await calls_since(db, "trasa", t0)
        lines.append(f"1 pierwsze calls={c1} n={len(first.candidates)} {row_text(first.candidates)}")
        t1 = datetime.now(UTC)
        second = await service.lookup_cached(user, profile_id, "trasa", annotate=False)
        await db.commit()
        c2 = await calls_since(db, "trasa", t1)
        same = [dict(c) for c in second.candidates] == [dict(c) for c in first.candidates]
        lines.append(f"2 powtorzenie calls={c2} te-same={same}")
        added_total = 0
        clicks = 0
        previous = [dict(c) for c in second.candidates]
        while clicks < 6:
            clicks += 1
            t = datetime.now(UTC)
            more = await service.lookup_expand(user.id, profile_id, "trasa", more=True)
            await db.commit()
            await asyncio.sleep(1.0)
            used = await calls_since(db, "trasa", t)
            current = [dict(c) for c in more.candidates]
            added = more.added
            added_total += added or 0
            lines.append(
                f"3.{clicks} wiecej calls={used} added={added} exhausted={more.suggestions_exhausted} {row_text(current)}"
            )
            if added == 1:
                lines.append("     -> jedno-haslo-na-klikniecie")
            if current[: len(previous)] != previous and previous:
                lines.append("     -> stare-wiersze-nie-zostaly-na-gorze")
            previous = current
            if more.suggestions_exhausted or not added:
                break
        t3 = datetime.now(UTC)
        third = await service.lookup_cached(user, profile_id, "trasa", annotate=False)
        await db.commit()
        c3 = await calls_since(db, "trasa", t3)
        lines.append(
            f"4 po-dociaganiu calls={c3} n={len(third.candidates)} exhausted={third.suggestions_exhausted}"
        )
        other = (
            await db.execute(
                text(
                    "select count(*) from lookup_query_cache where lang_pair = 'pl>ru' and input_norm = :k"
                ),
                {"k": normalize_lookup_query("droga")},
            )
        ).scalar()
        lines.append(f"7 zapis-pl>ru-dla-droga count={other}")

    text_out = "\n".join(lines)
    with open(OUT, "w", encoding="utf-8") as handle:
        handle.write(text_out)
    print(text_out)


asyncio.run(main())
