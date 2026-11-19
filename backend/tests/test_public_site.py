"""Public site pages (E-001/F-007/T-004): no database needed."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.services import legal_docs


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


@pytest.mark.parametrize("path", ["/", "/privacy", "/terms", "/legal", "/support"])
def test_pages_render_with_security_headers(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    html = response.text
    assert "<script" not in html
    assert "http://" not in html and "https://" not in html


def test_language_selection_and_honest_fallback(client):
    assert "Regulamin" in client.get("/terms?lang=pl").text
    assert "Condiciones de uso" in client.get("/terms?lang=es").text
    german = client.get("/terms", headers={"Accept-Language": "de-DE"}).text
    assert "Terms of Use" in german
    assert "not available in your language" in german
    assert "not available in your language" not in client.get("/terms?lang=en").text


def test_documents_are_served_only_for_known_versions(client):
    version = legal_docs.current_version("terms")
    ok = client.get(f"/documents/terms/{version}/pl")
    assert ok.status_code == 200
    assert legal_docs.digest("terms", "pl")[:16] in ok.text
    for bad in (
        f"/documents/terms/1999-01-01/pl",
        f"/documents/other/{version}/pl",
        f"/documents/terms/{version}/ja",
        f"/documents/terms/{version}/..",
    ):
        assert client.get(bad).status_code == 404


def test_operator_data_comes_from_settings_never_hardcoded(client, monkeypatch):
    unset = client.get("/support").text
    assert "[not configured]" in unset
    monkeypatch.setattr(get_settings(), "support_email", "help@example.test")
    monkeypatch.setattr(get_settings(), "operator_name", "Example Operator")
    assert "help@example.test" in client.get("/support").text
    assert "Example Operator" in client.get("/privacy").text


def test_assetlinks_lists_only_configured_fingerprints(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "android_cert_sha256", "")
    assert client.get("/.well-known/assetlinks.json").json() == []
    monkeypatch.setattr(get_settings(), "android_cert_sha256", "aa:bb, cc:dd")
    target = client.get("/.well-known/assetlinks.json").json()[0]["target"]
    assert target["package_name"] == "com.vocabulario.app"
    assert target["sha256_cert_fingerprints"] == ["AA:BB", "CC:DD"]


def test_every_text_exists_in_all_published_languages():
    from app.public_web.legal_texts import DOCUMENTS
    from app.public_web.site_texts import SITE_TEXTS

    assert {len(set(texts)) for texts in SITE_TEXTS.values()} == {len(SITE_TEXTS["en"])}
    for kind, locales in DOCUMENTS.items():
        assert set(locales) == set(legal_docs.LEGAL_LOCALES), kind
        assert len({len(locales[loc]["sections"]) for loc in locales}) == 1, kind
