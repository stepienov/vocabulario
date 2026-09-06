"""History helpers after restore/self-edit removal."""

from app.services.card_corrections import _diff_summary, history_event_response


def test_diff_summary_lemma_gloss():
    before = {"lemma_l2": "hablar", "pos": "verb", "gloss_primary": "mówić"}
    after = {"lemma_l2": "hablár", "pos": "verb", "gloss_primary": "gadać"}
    text = _diff_summary(before, after)
    assert "hablar" in text
    assert "hablár" in text
    assert "mówić" in text


def test_diff_summary_includes_word_family():
    before = {"content": {"word_family_l2": [{"gloss_l1": "przerywaność"}]}}
    after = {"content": {"word_family_l2": [{"gloss_l1": "przerywalność"}]}}
    text = _diff_summary(before, after)
    assert "word family" in text


def test_history_event_cannot_restore():
    event = type("E", (), {
        "id": "1",
        "card_id": "2",
        "event_type": "self_edit_applied",
        "actor": "user",
        "result_code": None,
        "summary": "x",
        "payload": {},
        "created_at": None,
    })()
    payload = history_event_response(event, [event])
    assert payload["can_restore"] is False
