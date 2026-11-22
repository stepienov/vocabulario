"""One-time account pages behind the e-mail links (E-001/F-004/T-002, step 3)."""

import re

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.public_web.texts import KEYS, PAGE_TEXTS
from app.services.mail_templates import SUPPORTED_LOCALES

PAGES = ("/account/verify-email", "/account/reset-password")


@pytest.fixture
async def client():
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


def _html_lang(response) -> tuple[str, str]:
    match = re.search(r'<html lang="([^"]+)" dir="([^"]+)">', response.text)
    assert match, response.text[:200]
    return match.group(1), match.group(2)


def test_every_locale_has_every_text_and_valid_placeholders():
    assert set(PAGE_TEXTS) == set(SUPPORTED_LOCALES)
    for locale, texts in PAGE_TEXTS.items():
        assert set(texts) == set(KEYS), locale
        for key, text in texts.items():
            assert text.strip(), (locale, key)
            text.format(app="Vocabulario", min=15, max=128)


@pytest.mark.parametrize("path", PAGES)
async def test_page_renders_with_security_headers_and_no_token_use(client, path):
    response = await client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    csp = response.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "'unsafe-inline'" not in csp
    # Only JSON data inline; executable code comes from the static file allowed by CSP.
    assert '<script src="/account/assets/account.js"></script>' in response.text
    assert re.findall(r"<script(?![^>]*(?:src=|application/json))", response.text) == []
    assert 'id="action-form" novalidate hidden' in response.text
    assert "noindex" in response.text


async def test_reset_page_has_password_fields_and_api_path(client):
    response = await client.get("/account/reset-password?lang=pl")
    assert _html_lang(response) == ("pl", "ltr")
    assert response.text.count('autocomplete="new-password"') == 2
    assert 'data-api="/api/v1/auth/password-reset/confirm"' in response.text
    assert "Ustaw nowe hasło" in response.text
    assert "Co najmniej 15 znaków" in response.text

    verify = await client.get("/account/verify-email?lang=pl")
    assert 'data-api="/api/v1/auth/email-verification/confirm"' in verify.text
    assert "new-password" not in verify.text


@pytest.mark.parametrize(
    ("query", "accept", "expected"),
    [
        ("?lang=pt-rBR", "de", ("pt-BR", "ltr")),
        ("?lang=ar", None, ("ar", "rtl")),
        ("?lang=xx", "de", ("en", "ltr")),
        ("", "xx-YY, fr-CA;q=0.8, en;q=0.5", ("fr", "ltr")),
        ("", "en-GB, de;q=0.9", ("en", "ltr")),
        ("", "de;q=0, ja;q=0.4", ("ja", "ltr")),
        ("", "*, q", ("en", "ltr")),
        ("", None, ("en", "ltr")),
    ],
)
async def test_language_choice(client, query, accept, expected):
    headers = {"Accept-Language": accept} if accept else {}
    response = await client.get(f"/account/verify-email{query}", headers=headers)
    assert _html_lang(response) == expected


async def test_texts_are_escaped_json_and_assets_are_served(client):
    response = await client.get("/account/reset-password?lang=fr")
    match = re.search(r'<script type="application/json" id="texts">(.*?)</script>', response.text)
    assert match and "\\u0027" in match.group(1)  # apostrophes escaped by tojson

    script = await client.get("/account/assets/account.js")
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert "history.replaceState" in script.text
    style = await client.get("/account/assets/account.css")
    assert style.status_code == 200 and "text/css" in style.headers["content-type"]


async def test_pages_accept_only_get(client):
    response = await client.post("/account/reset-password", json={})
    assert response.status_code == 405
    assert (await client.post("/account/delete-account", json={})).status_code == 405


async def test_email_change_is_not_available(client):
    assert (await client.get("/account/change-email")).status_code == 404
    assert (await client.post("/api/v1/auth/email-change/confirm", json={"token": "old"})).status_code == 404
    assert (await client.post("/api/v1/auth/email-change/request", json={})).status_code == 404


DELETION_PAGES = (
    "/delete-account",
    "/account/delete-account",
    "/account/cancel-deletion",
    "/account/deletion-status",
)


@pytest.mark.parametrize("path", DELETION_PAGES)
async def test_deletion_pages_render_without_acting(client, path):
    response = await client.get(path + "?lang=pl")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "'unsafe-inline'" not in response.headers["content-security-policy"]
    assert '<script src="/account/assets/account_deletion.js"></script>' in response.text
    assert re.findall(r"<script(?![^>]*(?:src=|application/json))", response.text) == []
    assert 'data-api="/api/v1/account-deletion"' in response.text
    assert 'id="action-form" novalidate hidden' in response.text
    assert _html_lang(response) == ("pl", "ltr")


async def test_deletion_script_keeps_token_and_password_out_of_storage(client):
    script = await client.get("/account/assets/account_deletion.js")
    assert script.status_code == 200
    assert "history.replaceState" in script.text
    assert script.text.count("sessionStorage") == 3  # only the status receipt is stored
