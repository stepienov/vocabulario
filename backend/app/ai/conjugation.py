"""Stałe i schemat pełnej koniugacji czasownika (zapis w bazie przy dodaniu słowa)."""

# Wszystkie czasy zapisywane w karcie — niezależnie od preferencji użytkownika.
ALL_CONJUGATION_TENSES: list[str] = [
    "presente",
    "preterito_perfecto",
    "preterito_indefinido",
    "preterito_imperfecto",
    "futuro_simple",
    "condicional_simple",
    "presente_subjuntivo",
    "imperfecto_subjuntivo",
    "futuro_subjuntivo",
    "preterito_pluscuamperfecto",
    "condicional_compuesto",
    "futuro_perfecto",
    "imperativo_afirmativo",
    "imperativo_negativo",
]

NON_FINITE_FORMS: list[str] = ["gerundio", "participio"]

# Domyślnie pokazywane w UI (reszta z profilu użytkownika).
DEFAULT_DISPLAY_TENSES: list[str] = ["presente", *NON_FINITE_FORMS]

PERSON_KEYS = ["yo", "tú", "él", "nosotros", "vosotros", "ellos"]

CONJUGATION_PROMPT_BLOCK = """
Dla czasowników (pos=verb) pole conjugation MUSI zawierać PEŁNĄ odmianę — wszystkie czasy poniżej,
formy nieosobowe oraz konstrukcje peryfrazyczne, w których TEN KONKRETNY czasownik (lemat: {lemma})
jest głową znaczeniową.
Użytkownicy wybierają w aplikacji, które czasy widzieć — w bazie musi być komplet.

Wymagane czasy w conjugation.tenses (każdy z osobami: yo, tú, él, nosotros, vosotros, ellos):
{tense_list}

Formy nieosobowe w conjugation.non_finite:
- gerundio (np. hablando)
- participio (np. hablado)

Konstrukcje w conjugation.periphrases — tablica obiektów z polami:
- id (np. dejar_de, volver_a, desarrollarse, contar_con)
- formula_l2 (np. "dejar de + infinitivo", "desarrollarse")
- gloss_l1 — znaczenie tej konstrukcji po polsku (wynikające z lematu {lemma}, nie z auxiliariusza)
- examples — tablica {{"l2": "...", "l1": "..."}}; zdanie MUSI ilustrować konstrukcję z lematem {lemma}

Zasady periphrases (KRYTYCZNE):
- Tylko konstrukcje, w których ZNACZENIE wynika z lematu „{lemma}”, nie z czasownika pomocniczego.
- ZAKAZANE (to peryfrazy auxiliariuszy, NIE dodawaj ich):
  * estar + gerundio (znaczenie: „być w trakcie” — decyduje estar)
  * ir + gerundio (znaczenie: stopniowość — decyduje ir)
  * haber + participio (czas złożony — decyduje haber)
  * tener que + infinitivo (modalność — decyduje tener)
- DOZWOLONE tylko gdy lemat niesie idiom:
  * dejar → „dejar de + infinitivo”
  * volver → „volver a + infinitivo”
  * acabar → „acabar de + infinitivo”
  * contar → „contar con + …”
  * forma zwrotna lematu, jeśli zmienia znaczenie (np. desarrollarse dla desarrollar)
- Jeśli czasownik nie ma naturalnych konstrukcji idiomatycznych → periphrases: [] (pusta tablica).
- Nie dodawaj peryfraz „na siłę”. Max 6 pozycji.
- gloss_l1 opisuje znaczenie KONSTRUKCJI z tym lematem, nie aspekt gramatyczny auxiliariusza.

Format conjugation:
{{
  "non_finite": {{"gerundio": "...", "participio": "..."}},
  "tenses": {{
    "presente": {{"yo":"...","tú":"...","él":"...","nosotros":"...","vosotros":"...","ellos":"..."}},
    "...": {{}}
  }},
  "periphrases": [
    {{
      "id": "dejar_de",
      "formula_l2": "dejar de + infinitivo",
      "gloss_l1": "przestać coś robić",
      "examples": [{{"l2": "Dejé de fumar.", "l1": "Rzuciłem palenie."}}]
    }}
  ]
}}

Dla nie-czasowników: conjugation = null.
""".strip()


def conjugation_rules_for_prompt(lemma: str) -> str:
    return CONJUGATION_PROMPT_BLOCK.format(
        lemma=lemma,
        tense_list=", ".join(ALL_CONJUGATION_TENSES),
    )
