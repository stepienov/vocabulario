from app.core.app_log_middleware import should_capture_http_body, slim_debug_http_body
from app.services.app_log import (
    category_for_path,
    is_noisy_get,
    sanitize_payload,
    should_log_http,
)


def test_category_for_path():
    assert category_for_path("/api/v1/lookup") == "lookup"
    assert category_for_path("/api/v1/imports/jobs") == "import"
    assert category_for_path("/api/v1/lists") == "lists"
    assert category_for_path("/api/v1/cards/abc/move") == "cards"
    assert category_for_path("/api/v1/me/settings") == "settings"
    assert category_for_path("/api/v1/srs/review") == "srs"
    assert category_for_path("/api/v1/auth/login") == "auth"


def test_noisy_get_skips_polls_but_not_mutations():
    assert is_noisy_get("GET", "/api/v1/lists")
    assert is_noisy_get("GET", "/api/v1/lists/abc/words")
    assert is_noisy_get("GET", "/api/v1/imports/jobs/abc/progress")
    assert not is_noisy_get("POST", "/api/v1/lists")
    assert not is_noisy_get("DELETE", "/api/v1/lists/abc")
    assert not is_noisy_get("POST", "/api/v1/lookup")


def test_should_log_http_errors_and_slow_polls():
    assert should_log_http("GET", "/api/v1/lists", 500, 10)
    assert should_log_http("GET", "/api/v1/lists", 200, 2500)
    assert not should_log_http("GET", "/api/v1/lists", 200, 20)
    assert should_log_http("POST", "/api/v1/lookup", 200, 20)
    assert should_log_http("DELETE", "/api/v1/cards/x", 204, 20)


def test_sanitize_payload_redacts_secrets():
    out = sanitize_payload(
        {"password": "secret", "lemma": "el resultado", "authorization": "Bearer abc"}
    )
    assert out["password"] == "[redacted]"
    assert out["authorization"] == "[redacted]"
    assert out["lemma"] == "el resultado"


def test_capture_lookup_and_card_bodies_only():
    assert should_capture_http_body("POST", "/api/v1/lookup")
    assert should_capture_http_body("POST", "/api/v1/lookup/expand")
    assert should_capture_http_body("POST", "/api/v1/cards")
    assert should_capture_http_body(
        "POST", "/api/v1/cards/11111111-1111-1111-1111-111111111111/retry-enrichment"
    )
    assert not should_capture_http_body("POST", "/api/v1/cards/x/move")
    assert not should_capture_http_body("GET", "/api/v1/lookup")


def test_slim_debug_http_body_keeps_short_fields():
    body = slim_debug_http_body(
        "/api/v1/lookup",
        {"text": "site", "profile_id": "abc", "password": "nope"},
    )
    assert body == {"text": "site", "profile_id": "abc"}
    retry = slim_debug_http_body(
        "/api/v1/cards/aaaa/retry-enrichment",
        {},
    )
    assert retry["card_id"] == "aaaa"
