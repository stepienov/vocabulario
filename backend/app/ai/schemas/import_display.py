"""JSON schema — analiza layoutu importowanych fiszek (role pól + bloki UI)."""


_BLOCK_TYPES = [
    "title",
    "paragraph",
    "bilingual",
    "list",
    "table",
    "meta",
    "chip",
    "section",
    "divider",
    "pre",
]


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
                "rationale": {"type": "string"},
            },
            "required": [
                "prompt_style",
                "field_roles",
                "prompt_blocks",
                "answer_blocks",
                "answer_needs_structure",
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
