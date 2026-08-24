"""POS for multiword lookup headwords (phrase vs construction vs lemma).

Construction = peryfraza / wzorzec z luką (tener que, be going to, volver a + inf).
Phrase = stały zwrot / lokucja (pagar a plazos, pedir perdón, look up).
Peryfraza NIE jest osobnym POS — to construction.
"""

from __future__ import annotations

from app.lsp.constants import normalize_l2_code
from app.lsp.lang_utils import articles_for
from app.services.pos_normalize import normalize_pos_bucket

_SLOT = frozenset(
    {
        "algo",
        "alguien",
        "something",
        "somebody",
        "someone",
        "anything",
        "anyone",
        "etwas",
        "jemand",
        "irgendwas",
        "qualcosa",
        "qualcuno",
        "alguém",
        "coś",
        "ktoś",
        "что-то",
        "кто-то",
        "何か",
        "誰か",
    }
)
_SLOT_PAIRS = frozenset(
    {
        ("quelque", "chose"),
        ("quelqu", "un"),
        ("alguna", "cosa"),
        ("alguma", "coisa"),
        ("bir", "şey"),
    }
)

_REFLEX = frozenset(
    {
        "se",
        "me",
        "te",
        "nos",
        "os",
        "sich",
        "mich",
        "dich",
        "uns",
        "euch",
        "si",
        "mi",
        "ti",
        "ci",
        "vi",
        "s'",
    }
)

# Prefiksy peryfraz. Najdłuższe pierwsze przy matchu.
# Open = reszta to luka (inf / algo / zdanie). Closed = tylko dokładny wzorzec
# albo wzorzec + inf/slot; konkretny rzeczownik po przyimku = phrase.
_OPEN_PREFIXES: dict[str, tuple[tuple[str, ...], ...]] = {
    "es": (
        ("estar", "a", "punto", "de"),
        ("tener", "ganas", "de"),
        ("tener", "que"),
        ("hay", "que"),
        ("haber", "que"),
        ("haber", "de"),
        ("acabar", "de"),
        ("dejar", "de"),
        ("tener", "de"),
    ),
    "fr": (
        ("être", "en", "train", "de"),
        ("être", "sur", "le", "point", "de"),
        ("venir", "de"),
        ("avoir", "à"),
        ("avoir", "a"),
        ("falloir", "que"),
        ("être", "à"),
    ),
    "de": (
        ("im", "begriff", "sein"),
        ("anfangen", "zu"),
        ("aufhören", "zu"),
        ("beginnen", "zu"),
        ("haben", "zu"),
        ("sein", "zu"),
    ),
    "en": (
        ("be", "going", "to"),
        ("be", "able", "to"),
        ("be", "about", "to"),
        ("be", "supposed", "to"),
        ("going", "to"),
        ("have", "to"),
        ("used", "to"),
        ("ought", "to"),
        ("need", "to"),
    ),
    "it": (
        ("stare", "per"),
        ("avere", "da"),
        ("finire", "di"),
        ("smettere", "di"),
        ("continuare", "a"),
        ("stare", "per"),
    ),
    "pt-br": (
        ("ter", "que"),
        ("ter", "de"),
        ("haver", "de"),
        ("acabar", "de"),
        ("deixar", "de"),
    ),
    "pt-pt": (
        ("ter", "que"),
        ("ter", "de"),
        ("haver", "de"),
        ("acabar", "de"),
        ("deixar", "de"),
    ),
    "pl": (
        ("być", "w", "stanie"),
        ("mieć", "zamiar"),
        ("mieć", "obowiązek"),
    ),
    "ru": (
        ("быть", "в", "состоянии"),
        ("собираться"),
    ),
    "ar": (
        ("يجب", "أن"),
        ("لابد", "أن"),
        ("على", "وشك"),
    ),
    "hi": (
        ("सकता", "है"),
        ("चाहिए"),
    ),
    "tr": (
        ("zorunda", "olmak"),
        ("mecbur", "olmak"),
    ),
    "vi": (
        ("có", "thể"),
        ("sắp"),
    ),
}

# ir a / volver a: construction gdy dokładne LUB dopełnienie to inf/slot.
_A_INF_PREFIXES: dict[str, tuple[tuple[str, ...], ...]] = {
    "es": (
        ("ir", "a"),
        ("volver", "a"),
        ("ponerse", "a"),
        ("echar", "a"),
        ("romper", "a"),
        ("estar", "por"),
    ),
    "fr": (("aller",),),  # aller + inf handled by infinitive rest; aller seul = verb
    "it": (("cominciare", "a"), ("iniziare", "a"), ("tornare", "a")),
    "pt-br": (("ir", "a"), ("voltar", "a"), ("pôr-se", "a"), ("por-se", "a")),
    "pt-pt": (("ir", "a"), ("voltar", "a"), ("pôr-se", "a"), ("por-se", "a")),
}

_UNSPACED_CONSTRUCTION: dict[str, tuple[str, ...]] = {
    "ja": (
        "なければならない",
        "てはいけない",
        "ことができる",
        "てしまう",
        "ている",
        "ておく",
        "てみる",
    ),
    "ko": ("아야 하다", "어야 하다", "고 있다", "ㄹ 수 있다", "지 않다"),
    "zh": ("不得不", "越来越", "正在"),
}

_PHRASE_EXAMPLES: dict[str, str] = {
    "es": "pagar a plazos, pedir perdón, hacer la cama",
    "en": "look up, give up, take care of",
    "fr": "avoir peur, faire attention, tout de suite",
    "de": "Guten Tag, sich beeilen (as locution), im Grunde",
    "it": "avere fame, fare attenzione",
    "pt-br": "ter pressa, fazer as malas",
    "pt-pt": "ter pressa, fazer as malas",
    "pl": "mieć na myśli, zwracać uwagę",
    "ru": "обращать внимание, иметь в виду",
    "zh": "对不起, 没关系",
    "ja": "お願いします, ただいま",
    "ko": "잘 지내, 고맙습니다",
    "ar": "من فضلك, على الرحب",
    "hi": "ध्यान देना",
    "tr": "göz atmak, karar vermek",
    "vi": "làm ơn, chú ý",
}

_CONSTRUCTION_EXAMPLES: dict[str, str] = {
    "es": "tener que, ir a + inf, volver a hacer algo, hay que",
    "en": "have to, be going to, used to, be able to",
    "fr": "venir de, être en train de, aller + inf",
    "de": "anfangen zu, haben zu",
    "it": "stare per, smettere di, continuare a",
    "pt-br": "ter que, acabar de, voltar a + inf",
    "pt-pt": "ter que, acabar de, voltar a + inf",
    "pl": "być w stanie, mieć zamiar",
    "ru": "быть в состоянии",
    "zh": "不得不, 越来越",
    "ja": "ている, なければならない, ことができる",
    "ko": "고 있다, 아야 하다",
    "ar": "يجب أن",
    "hi": "सकता है",
    "tr": "zorunda olmak",
    "vi": "có thể",
}


def _lang(code: str | None) -> str:
    c = normalize_l2_code(code)
    return "pt-br" if c == "pt" else c


def _tokens(lemma: str) -> list[str]:
    raw = (lemma or "").strip()
    for sep in ("+", "·", "〜", "~"):
        raw = raw.replace(sep, " ")
    return [t.strip(".,;:!?\"'«»").lower() for t in raw.split() if t.strip(".,;:!?\"'«»")]


def _looks_like_infinitive(token: str, lang: str) -> bool:
    t = (token or "").lower()
    if lang in {"es", "pt-br", "pt-pt", "it"}:
        return t.endswith(("ar", "er", "ir", "arse", "erse", "irse", "arse"))
    if lang == "fr":
        return t.endswith(("er", "ir", "re", "oir"))
    if lang == "de":
        return t.endswith(("en", "eln", "ern", "n"))
    if lang == "pl":
        return t.endswith("ć")
    if lang == "ru":
        return t.endswith(("ть", "ти", "чь"))
    return False


def _rest_is_slot(rest: list[str]) -> bool:
    if not rest:
        return True
    if rest[0] in _SLOT:
        return True
    if len(rest) >= 2 and (rest[0], rest[1]) in _SLOT_PAIRS:
        return True
    return False


def _match_prefix(tokens: list[str], frames: tuple[tuple[str, ...], ...]) -> tuple[str, ...] | None:
    for frame in sorted(frames, key=len, reverse=True):
        n = len(frame)
        if len(tokens) >= n and tuple(tokens[:n]) == frame:
            return frame
    return None


def _is_reflexive_verb(tokens: list[str]) -> bool:
    if len(tokens) != 2:
        return False
    return tokens[0] in _REFLEX or tokens[1] in _REFLEX


def _unspaced_construction(lemma: str, lang: str) -> bool:
    raw = (lemma or "").strip()
    for frag in _UNSPACED_CONSTRUCTION.get(lang, ()):
        if frag and frag in raw:
            return True
    return False


def is_construction_headword(lemma: str, *, learning_lang: str | None) -> bool:
    lang = _lang(learning_lang)
    articles = articles_for(lang)
    raw = lemma or ""
    if any(ch in raw for ch in "+·〜~"):
        return True
    if _unspaced_construction(raw, lang):
        return True
    tokens = _tokens(raw)
    if not tokens:
        return False
    open_frames = _OPEN_PREFIXES.get(lang, ())
    frame = _match_prefix(tokens, open_frames)
    if frame:
        rest = tokens[len(frame) :]
        if not rest or _rest_is_slot(rest):
            return True
        if rest and _looks_like_infinitive(rest[0], lang):
            return True
        # tener que ir / have to go — but not "going to the store"
        if frame[-1] in {"que", "to", "zu"}:
            dets = articles | {"the", "a", "an", "my", "your", "his", "her", "their", "this", "that"}
            return bool(rest) and rest[0] not in dets
        return False

    a_frames = _A_INF_PREFIXES.get(lang, ())
    frame = _match_prefix(tokens, a_frames)
    if frame:
        rest = tokens[len(frame) :]
        if not rest:
            return True
        if _rest_is_slot(rest):
            return True
        if rest and _looks_like_infinitive(rest[0], lang):
            return True
        return False

    # aller + infinitive (FR) — single-token prefix
    if lang == "fr" and len(tokens) >= 2 and tokens[0] == "aller":
        return _looks_like_infinitive(tokens[1], lang) or tokens[1] in _SLOT

    return False


def refine_lookup_pos(
    lemma: str,
    pos: str | None,
    *,
    learning_lang: str | None,
) -> str | None:
    """Zwraca kanoniczny bucket; wielowyrazowy czasownik → phrase lub construction."""
    bucket = normalize_pos_bucket(pos)
    lang = _lang(learning_lang)
    tokens = _tokens(lemma)
    n = len(tokens)
    articles = articles_for(lang)

    if bucket in {"phrase", "construction"}:
        if is_construction_headword(lemma, learning_lang=lang):
            return "construction"
        return "phrase" if n >= 2 or _unspaced_construction(lemma, lang) else bucket

    if n <= 1:
        if is_construction_headword(lemma, learning_lang=lang):
            return "construction"
        return None if bucket == "unknown" else bucket

    if n == 2 and tokens[0].rstrip("'") in articles:
        return "noun" if bucket in {"noun", "unknown", "phrase"} else bucket

    if _is_reflexive_verb(tokens) and bucket in {"verb", "unknown"}:
        return "verb"

    if is_construction_headword(lemma, learning_lang=lang):
        return "construction"

    if bucket in {"verb", "unknown"}:
        return "phrase"
    if bucket in {"noun", "adj", "adv"} and n >= 2:
        return "phrase"
    return None if bucket == "unknown" else bucket


def lookup_multiword_pos_rules(learning_lang: str | None) -> str:
    lang = _lang(learning_lang)
    phrase_ex = _PHRASE_EXAMPLES.get(lang, _PHRASE_EXAMPLES["en"])
    constr_ex = _CONSTRUCTION_EXAMPLES.get(lang, _CONSTRUCTION_EXAMPLES["en"])
    return f"""MULTIWORD / PERIPHRASIS POS (in addition to single-word buckets)
- phrase: fixed collocation / locution WITHOUT a productive slot.
  Examples for this L2: {phrase_ex}
- construction: grammaticalized periphrasis or pattern WITH a slot
  (infinitive, algo/something, que/to/zu). Examples: {constr_ex}
- verb: ONE dictionary verb, or a 2-word reflexive (se laver, sich erinnern).
  NEVER tag "pagar a plazos" / "look up" / "tener que" as verb.
- Do not invent a separate pos "periphrase" / "expression" / "idiom":
  locution → phrase; periphrasis → construction.
- lemma stays the FULL multiword headword (never reduce to the base verb).
"""
