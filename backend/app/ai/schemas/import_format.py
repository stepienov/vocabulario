"""JSON schema — LLM zwraca instrukcję jak podzielić surowy plik/wklejkę na notatki."""


def import_format_schema() -> dict:
    return {
        "name": "import_format",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "already_segmented": {
                    "type": "boolean",
                    "description": (
                        "true = wejście jest już listą notatek z polami "
                        "(np. Anki notes/apkg) — NIE dzielić raw od nowa"
                    ),
                },
                "card_separator": {
                    "type": "string",
                    "enum": [
                        "newline",
                        "blank_lines",
                        "comma",
                        "semicolon",
                        "custom_string",
                        "none",
                    ],
                    "description": (
                        "Jak dzielić tekst na OSOBNE FISZKI. "
                        "newline = każda linia; blank_lines = puste linie; "
                        "comma = przecinek między hasłami (lista słów w jednej linii); "
                        "semicolon = znak ; między kartami (Quizlet „entre renglones”, "
                        "często CAŁY eksport w JEDNEJ linii); "
                        "custom_string = card_separator_value (np. === lub |); "
                        "none = nie dziel na karty tu (całość → row_mode)"
                    ),
                },
                "card_separator_value": {
                    "type": ["string", "null"],
                    "description": "Gdy card_separator=custom_string (np. ===)",
                },
                "row_mode": {
                    "type": "string",
                    "enum": [
                        "delimited",
                        "multiline_first_rest",
                        "single_line_as_note",
                        "whole_block_one_field",
                    ],
                    "description": (
                        "Jak w obrębie JEDNEJ fiszki wydzielić pola. "
                        "delimited = field_delimiter; "
                        "multiline_first_rest = 1. linia front, reszta tył; "
                        "single_line_as_note = cała karta = 1 pole; "
                        "whole_block_one_field = j.w."
                    ),
                },
                "field_delimiter": {
                    "type": "string",
                    "enum": ["tab", "comma", "semicolon", "none"],
                    "description": (
                        "Separator pól WEWNĄTRZ fiszki (Quizlet „entre término y definición”). "
                        "NIE mylić z card_separator."
                    ),
                },
                "field_split": {
                    "type": "string",
                    "enum": ["all", "first_only"],
                    "description": (
                        "all = split po każdym field_delimiter; "
                        "first_only = tylko PIERWSZY delimiter dzieli front/tył "
                        "(tył może zawierać przecinki — typowe w Quizlet)"
                    ),
                },
                "append_continuation_lines_to_answer": {
                    "type": "boolean",
                    "description": (
                        "Gdy delimited w trybie linii: linie BEZ delimitera zaraz po wierszu "
                        "doklej do odpowiedzi"
                    ),
                },
                "inferred_field_names": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                    "description": "Opcjonalne nazwy pól po Twojej segmentacji",
                },
                "preview_notes": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "description": (
                        "3–8 przykładów notatek PO zastosowaniu Twojej instrukcji "
                        "(każda = [front, back, …])"
                    ),
                },
                "rationale": {
                    "type": "string",
                    "description": (
                        "Po polsku: jaki to format, jak dzielić na fiszki, "
                        "co jest frontem/tyłem"
                    ),
                },
            },
            "required": [
                "already_segmented",
                "card_separator",
                "card_separator_value",
                "row_mode",
                "field_delimiter",
                "field_split",
                "append_continuation_lines_to_answer",
                "inferred_field_names",
                "preview_notes",
                "rationale",
            ],
        },
    }
