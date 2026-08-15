"""Display v2: HTML structure parser + schema validation + layout fallback."""

from __future__ import annotations

from app.ai.schemas.import_display import validate_import_display_payload
from app.services.import_display import html_structure_blocks, _mock_display_analysis
from app.services.import_package import RawImportDeck


def test_html_table_becomes_table_block():
    html = """
    <table>
      <tr><th>yo</th><th>tú</th></tr>
      <tr><td class="form">hablo</td><td class="form">hablas</td></tr>
    </table>
    """
    blocks = html_structure_blocks(html)
    assert blocks is not None
    assert blocks[0]["type"] == "table"
    assert blocks[0]["headers"] == ["yo", "tú"]
    assert blocks[0]["rows"] == [["hablo", "hablas"]]
    assert blocks[0]["semantic"] == "conjugation"


def test_html_list_becomes_list_block():
    html = "<ul><li>uno</li><li>dos</li></ul>"
    blocks = html_structure_blocks(html)
    assert blocks is not None
    assert blocks[0]["type"] == "list"
    assert blocks[0]["items"] == ["uno", "dos"]


def test_plain_text_returns_none():
    assert html_structure_blocks("just text") is None


def test_validate_import_display_payload_ok():
    ok, reason = validate_import_display_payload(
        {
            "prompt_style": "word",
            "field_roles": [],
            "prompt_blocks": [{"type": "headword"}],
            "answer_blocks": [],
            "answer_needs_structure": False,
            "rationale": "ok",
        }
    )
    assert ok
    assert reason == ""


def test_validate_import_display_payload_rejects_empty_prompt():
    ok, reason = validate_import_display_payload(
        {
            "prompt_style": "word",
            "field_roles": [],
            "prompt_blocks": [],
            "answer_blocks": [],
            "answer_needs_structure": False,
            "rationale": "x",
        }
    )
    assert not ok
    assert "empty" in reason


def test_mock_display_includes_bidirectional():
    deck = RawImportDeck(
        kind="notes",
        field_names=["Spanish", "Polish"],
        notes=[["hablar", "mówić"]],
    )
    analysis = _mock_display_analysis(deck)
    assert "bidirectional" in analysis
    assert analysis["bidirectional"] is True
