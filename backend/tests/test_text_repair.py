from app.core.text_repair import repair_display_text, repair_strings


def test_repairs_polish_quotes():
    raw = "S\u0142owo \u00d4\u00c7\u00d7casa\u00d4\u00c7\u0141 ko\u0144czy si\u0119 na a."
    assert repair_display_text(raw) == "S\u0142owo \u201ecasa\u201d ko\u0144czy si\u0119 na a."


def test_walks_nested_content():
    fixed = repair_strings({"l1": "\u00d4\u00c7\u00d7x\u00d4\u00c7\u0141"})
    assert fixed["l1"] == "\u201ex\u201d"
