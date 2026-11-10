"""Loose second-pass lookup: missing senses, one-edit typos, inflection."""
import asyncio
import json
import time
from dataclasses import dataclass

from app.services.llm import LLMService

SYSTEM = """Jesteś słownikiem. Zwracasz wyłącznie JSON.

Dostajesz język 1, język 2, hasło i pary, które już są na ekranie.
Najpierw wybierz dokładnie jedno zamierzone hasło. Potem zwróć tylko jego brakujące znaczenia.

Jeśli wpisane hasło jest prawdziwym słowem w języku 1 albo w języku 2, zamierzone hasło to właśnie ono.
Nie szukaj wtedy podobnych słów.
Sens, który już jest na liście, jest zamknięty. Nie dodawaj drugiego słowa na ten sam sens.
Dodaj inny sens tego samego hasła.
Jeśli nie jest prawdziwym słowem, popraw je tylko gdy różnica to dokładnie jedno z tych:
jedna dodana litera, jedna usunięta litera, jedna zamieniona litera albo dwie sąsiednie litery przestawione, także na końcu słowa.
Policz tę różnicę na literach wpisu. Większa różnica, cyfra albo kropka: nie ma hasła.
Osobno sprawdź drugi język: ten sam ciąg znaków może być tam innym słowem. To jest brakujący sens, nie synonim.
Nie bierz słowa podobnego brzmieniem ani z tym samym początkiem.

Zwróć znaczenia tego jednego hasła, których nie ma na liście. Jedno hasło, żadnego drugiego.
Nie powtarzaj pokazanych par.
word pisz tylko w języku 2. translation pisz tylko w języku 1. To mają być dwa różne słowa.
Nie wymyślaj słów. Przymiotnik to nie rzeczownik.
Rzeczownik w języku 2 zaczyna się od rodzajnika (el/la, le/la/l', der/die/das).
Gdy nie ma nic nowego: {"pairs":[]}
W przeciwnym razie: {"pairs":[{"word":"...","pos":"...","translation":"..."}]}"""


@dataclass(frozen=True)
class Case:
    language_1: str
    language_2: str
    query: str
    already: tuple[tuple[str, str], ...]
    want_any: frozenset[str]
    forbid: frozenset[str] = frozenset()
    expect_empty: bool = False


CASES = [
    Case("polski", "hiszpański", "ser", (("el queso", "ser"), ("ser", "być")), frozenset({"istota", "byt"})),
    Case("polski", "hiszpański", "droga", (("la carretera", "droga"),), frozenset({"narkotyk"}), frozenset({"cara", "caro", "querida", "via", "ruta", "camino"})),
    Case("polski", "hiszpański", "serr", (), frozenset({"queso", "byc", "ser"})),
    Case("polski", "hiszpański", "sre", (), frozenset({"queso", "byc", "ser"})),
    Case("polski", "hiszpański", "ser3", (), frozenset(), expect_empty=True),
    Case("polski", "hiszpański", "drogi", (), frozenset({"caro", "camino", "carretera"})),
    Case("francuski", "angielski", "caht", (), frozenset({"cat", "chat"})),
    Case("niemiecki", "angielski", "Gift", (("poison", "Gift"),), frozenset({"geschenk"})),
]


def fold(value: str) -> str:
    text = (value or "").casefold()
    for src, dst in {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z", "ä": "a", "ö": "o", "ü": "u"}.items():
        text = text.replace(src, dst)
    return "".join(ch for ch in text if ch.isalnum() or ch.isspace())


def bag(rows: list[dict]) -> set[str]:
    out: set[str] = set()
    for row in rows:
        for key in ("word", "translation"):
            parts = fold(str(row.get(key) or "")).split()
            out.update(parts)
            if len(parts) >= 2 and parts[0] in {"el", "la", "le", "der", "die", "das", "the", "a"}:
                out.add(parts[1])
    return out


def judge(case: Case, rows: list[dict]) -> list[str]:
    if case.expect_empty:
        return [f"zwrocil-{len(rows)}"] if rows else []
    found = bag(rows)
    problems = []
    if not found & case.want_any:
        problems.append("brak:" + ",".join(sorted(case.want_any)))
    hit = found & case.forbid
    if hit:
        problems.append("zle:" + ",".join(sorted(hit)))
    return problems


async def call(llm: LLMService, effort: str, case: Case) -> dict:
    shown = "\n".join(f"- word={w}; translation={t}" for w, t in case.already) or "(brak)"
    user = (
        f"Język 1: {case.language_1}\nJęzyk 2: {case.language_2}\n"
        f"Hasło: {case.query}\nJuż pokazane:\n{shown}"
    )
    t0 = time.perf_counter()
    resp = await llm.client.chat.completions.create(
        model="gpt-6-sol",
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        max_completion_tokens=400,
        reasoning_effort=effort,
        service_tier="priority",
    )
    ms = round((time.perf_counter() - t0) * 1000)
    data = json.loads(resp.choices[0].message.content or "{}")
    rows = [r for r in (data.get("pairs") or []) if isinstance(r, dict)] if isinstance(data, dict) else []
    problems = judge(case, rows)
    return {"ok": not problems, "effort": effort, "q": case.query, "ms": ms, "problems": problems, "pairs": rows}


async def main() -> None:
    llm = LLMService()
    rows = await asyncio.gather(*(call(llm, "none", case) for case in CASES for _ in range(3)))
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    roll: dict[str, list[int]] = {}
    for row in rows:
        slot = roll.setdefault(row["effort"], [0, 0, 0])
        slot[1] += 1
        slot[0] += int(row["ok"])
        slot[2] += row["ms"]
    print(json.dumps({k: {"passed": v[0], "total": v[1], "avg_ms": round(v[2] / v[1])} for k, v in roll.items()}))


if __name__ == "__main__":
    asyncio.run(main())
