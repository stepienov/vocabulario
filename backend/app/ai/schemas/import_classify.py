"""JSON schema — klasyfikacja zaimportowanych notatek → entry_kind / headword."""


def import_classify_schema() -> dict:
    return {
        "name": "import_classify",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "index": {
                                "type": "integer",
                                "description": "Indeks notatki z wejścia (0-based)",
                            },
                            "valid": {
                                "type": "boolean",
                                "description": "false = śmieć / brak treści L2",
                            },
                            "entry_kind": {
                                "type": "string",
                                "enum": [
                                    "lemma",
                                    "phrase",
                                    "construction",
                                    "sentence",
                                    "other",
                                ],
                            },
                            "headword_l2": {
                                "type": "string",
                                "description": "Hasło / zwrot w L2 do nauki",
                            },
                            "gloss_l1": {
                                "type": ["string", "null"],
                                "description": "Tłumaczenie / gloss z importu lub null",
                            },
                            "pos": {
                                "type": ["string", "null"],
                                "description": "np. verb, noun, phrase, construction",
                            },
                            "base_lemma": {
                                "type": ["string", "null"],
                                "description": "Opcjonalny lemat bazowy (volver dla volver a…)",
                            },
                            "pattern": {
                                "type": ["string", "null"],
                                "description": "np. volver a + infinitivo",
                            },
                            "invalid_reason": {
                                "type": ["string", "null"],
                            },
                        },
                        "required": [
                            "index",
                            "valid",
                            "entry_kind",
                            "headword_l2",
                            "gloss_l1",
                            "pos",
                            "base_lemma",
                            "pattern",
                            "invalid_reason",
                        ],
                    },
                },
                "rationale": {"type": "string"},
            },
            "required": ["entries", "rationale"],
        },
    }


def import_verify_lemmas_schema() -> dict:
    return {
        "name": "import_verify_lemmas",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "invalid": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "index": {"type": "integer"},
                            "reason": {"type": "string"},
                        },
                        "required": ["index", "reason"],
                    },
                }
            },
            "required": ["invalid"],
        },
    }


def import_adaptive_enrich_schema() -> dict:
    """Uproszczona bogata karta dla phrase/construction/sentence."""
    return {
        "name": "import_adaptive_enrich",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "lemma": {"type": "string"},
                "pos": {"type": ["string", "null"]},
                "pattern": {"type": ["string", "null"]},
                "related_lemma": {"type": ["string", "null"]},
                "ipa": {"type": ["string", "null"]},
                "meanings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "gloss_l1": {"type": "string"},
                            "synonyms_l1": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "usages": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "examples": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "l2": {"type": "string"},
                                        "l1": {"type": "string"},
                                        "cefr": {"type": "string"},
                                    },
                                    "required": ["l2", "l1", "cefr"],
                                },
                            },
                        },
                        "required": ["gloss_l1", "synonyms_l1", "usages", "examples"],
                    },
                },
                "notes": {"type": ["string", "null"]},
            },
            "required": [
                "lemma",
                "pos",
                "pattern",
                "related_lemma",
                "ipa",
                "meanings",
                "notes",
            ],
        },
    }
