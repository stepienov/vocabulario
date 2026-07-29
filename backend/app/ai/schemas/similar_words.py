from __future__ import annotations

MIN_SIMILAR_WORDS = 12

# Awaryjne dopełnienie, gdy pierwsza odpowiedź nie da 12 unikatów: pula słów
# z poziomu użytkownika, z której bierzemy tylko brakujące pozycje.
FILL_POOL_SIZE = 20

WORD_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "lemma": {"type": "string"},
        "pos": {"type": "string"},
        "gloss_l1": {"type": "string"},
    },
    "required": ["lemma", "pos", "gloss_l1"],
    "additionalProperties": False,
}


def similar_words_response_schema(*, count: int) -> dict:
    """Schema odpowiedzi. Uwaga: strict mode nie wspiera uniqueItems —
    unikalność wymuszamy promptem i deduplikacją po stronie backendu."""
    return {
        "name": f"similar_words_{count}",
        "schema": {
            "type": "object",
            "properties": {
                "similar_words": {
                    "type": "array",
                    "items": WORD_ITEM_SCHEMA,
                    "minItems": count,
                    "maxItems": count,
                },
            },
            "required": ["similar_words"],
            "additionalProperties": False,
        },
    }
