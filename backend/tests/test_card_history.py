"""History helpers after restore/self-edit removal."""

from app.services.card_corrections import history_event_response


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
