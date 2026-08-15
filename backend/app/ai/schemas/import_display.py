"""JSON schema — analiza layoutu importowanych fiszek (display v2)."""


# Zamknięty słownik + legacy (title/paragraph/pre/meta) dla wstecznej zgodności.
_BLOCK_TYPES = [
    "headword",
    "gloss",
    "bilingual",
    "list",
    "table",
    "note",
    "chip",
    "section",
    "divider",
    "text",
    # legacy
    "title",
    "paragraph",
    "meta",
    "pre",
]

_ALIGN = ["start", "center", None]
_SIZE = ["display", "lemma", "gloss", "body", "caption", None]
_SEMANTIC = [
    "headword",
    "translation",
    "example",
    "note",
    "conjugation",
    "pronunciation",
    "tags",
    None,
]


def _tts_schema() -> dict:
    return {
        "type": ["object", "null"],
        "additionalProperties": False,
        "properties": {
            "enabled": {"type": "boolean"},
            "lang": {"type": ["string", "null"]},
        },
        "required": ["enabled", "lang"],
    }


def _leaf_block_props() -> dict:
    return {
        "type": {"type": "string", "enum": _BLOCK_TYPES},
        "text": {"type": ["string", "null"]},
        "emphasis": {
            "type": ["string", "null"],
            "enum": ["lemma", "gloss", "plain", None],
        },
        "field_index": {"type": ["integer", "null"]},
        "l2_field_index": {"type": ["integer", "null"]},
        "l1_field_index": {"type": ["integer", "null"]},
        "heading": {"type": ["string", "null"]},
        "collapsed": {"type": ["boolean", "null"]},
        "items": {"type": ["array", "null"], "items": {"type": "string"}},
        "headers": {"type": ["array", "null"], "items": {"type": "string"}},
        "rows": {
            "type": ["array", "null"],
            "items": {"type": "array", "items": {"type": "string"}},
        },
        "split": {
            "type": ["string", "null"],
            "enum": ["none", "paragraphs", "headings", None],
        },
        "align": {"type": ["string", "null"], "enum": _ALIGN},
        "size": {"type": ["string", "null"], "enum": _SIZE},
        "semantic": {"type": ["string", "null"], "enum": _SEMANTIC},
        "tts": _tts_schema(),
    }


_LEAF_REQUIRED = [
    "type",
    "text",
    "emphasis",
    "field_index",
    "l2_field_index",
    "l1_field_index",
    "heading",
    "collapsed",
    "items",
    "headers",
    "rows",
    "split",
    "align",
    "size",
    "semantic",
    "tts",
]


def _child_block_schema() -> dict:
    """Dziecko sekcji — bez zagnieżdżonych children (głębokość 1)."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": _leaf_block_props(),
        "required": _LEAF_REQUIRED,
    }


def _block_schema() -> dict:
    """Blok UI; section może mieć children (1 poziom)."""
    props = {
        **_leaf_block_props(),
        "children": {
            "type": ["array", "null"],
            "items": _child_block_schema(),
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": props,
        "required": [*_LEAF_REQUIRED, "children"],
    }


def import_display_schema() -> dict:
    return {
        "name": "import_display",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "prompt_style": {
                    "type": "string",
                    "enum": ["word", "phrase", "sentence", "html_block"],
                },
                "field_roles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "index": {"type": "integer"},
                            "name": {"type": ["string", "null"]},
                            "role": {
                                "type": "string",
                                "enum": [
                                    "prompt",
                                    "answer",
                                    "secondary",
                                    "example",
                                    "meta",
                                    "detail",
                                    "ignore",
                                ],
                            },
                        },
                        "required": ["index", "name", "role"],
                    },
                },
                "prompt_blocks": {
                    "type": "array",
                    "items": _block_schema(),
                    "description": "Szablon frontu — field_index wskazują pola notatki",
                },
                "answer_blocks": {
                    "type": "array",
                    "items": _block_schema(),
                    "description": "Szablon tyłu — field_index / bilingual / section",
                },
                "answer_needs_structure": {
                    "type": "boolean",
                    "description": (
                        "True gdy prawa strona jest długa/HTML/dziwna i wymaga "
                        "dodatkowego podziału (split/headings) zamiast jednego akapitu"
                    ),
                },
                "bidirectional": {
                    "type": "boolean",
                    "description": (
                        "True tylko gdy pewnie otagowano semantic=headword (L2) "
                        "i semantic=translation (L1)"
                    ),
                },
                "rationale": {"type": "string"},
            },
            "required": [
                "prompt_style",
                "field_roles",
                "prompt_blocks",
                "answer_blocks",
                "answer_needs_structure",
                "bidirectional",
                "rationale",
            ],
        },
    }


def import_answer_structure_schema() -> dict:
    """Jednorazowa analiza grubej prawej strony (sample) → jak dzielić tekst."""
    return {
        "name": "import_answer_structure",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "strategy": {
                    "type": "string",
                    "enum": ["paragraphs", "headings", "keep_pre", "sections_from_sample"],
                },
                "heading_hints": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Typowe nagłówki sekcji widoczne w próbce",
                },
                "sample_blocks": {
                    "type": "array",
                    "items": _block_schema(),
                    "description": "Przykładowy layout bloku dla PIERWSZEJ próbki (tekst już wypełniony)",
                },
                "rationale": {"type": "string"},
            },
            "required": ["strategy", "heading_hints", "sample_blocks", "rationale"],
        },
    }


def validate_import_display_payload(data: dict) -> tuple[bool, str]:
    """Lekka walidacja strukturalna wyjścia AI (nie pełny JSON Schema)."""
    if not isinstance(data, dict):
        return False, "not an object"
    for key in (
        "prompt_style",
        "field_roles",
        "prompt_blocks",
        "answer_blocks",
        "answer_needs_structure",
        "rationale",
    ):
        if key not in data:
            return False, f"missing {key}"
    if not isinstance(data.get("prompt_blocks"), list):
        return False, "prompt_blocks not a list"
    if not isinstance(data.get("answer_blocks"), list):
        return False, "answer_blocks not a list"
    if not data["prompt_blocks"]:
        return False, "prompt_blocks empty"
    # bidirectional opcjonalne w starych odpowiedziach — domyślnie false przy braku
    return True, ""
