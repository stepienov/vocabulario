"""JSON schema — analiza struktury importu Anki/CSV/Quizlet przez LLM."""


def import_structure_schema() -> dict:
    return {
        "name": "import_structure",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "strategy": {
                    "type": "string",
                    "enum": ["field_index", "html_class", "plain_list"],
                    "description": (
                        "field_index = stała kolumna/pole; "
                        "html_class = wyciągnij tekst z klasy CSS; "
                        "plain_list = każdy wiersz to już jedno hasło L2"
                    ),
                },
                "field_index": {
                    "type": ["integer", "null"],
                    "description": "0-based indeks pola z hasłem L2 (gdy strategy=field_index)",
                },
                "html_class": {
                    "type": ["string", "null"],
                    "description": "Klasa CSS z hasłem L2 (gdy strategy=html_class)",
                },
                "l2_field_label": {
                    "type": "string",
                    "description": (
                        "Krótka etykieta tego, skąd bierzesz hasło "
                        "(np. 'kolumna 0 / term Quizlet', 'pole Spanish', 'class answer-word')"
                    ),
                },
                "sample_headwords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "5–15 przykładów unikalnych haseł L2 po zastosowaniu strategii",
                },
                "unique_estimate": {
                    "type": "integer",
                    "description": "Szacunek unikalnych haseł L2 w całej talii",
                },
                "rationale": {
                    "type": "string",
                    "description": (
                        "Wyjaśnienie po polsku: co to za format, które pole to L2, "
                        "które to L1/odmiana/przykład, i jak powstanie karta Vocabulario"
                    ),
                },
            },
            "required": [
                "strategy",
                "field_index",
                "html_class",
                "l2_field_label",
                "sample_headwords",
                "unique_estimate",
                "rationale",
            ],
        },
    }
