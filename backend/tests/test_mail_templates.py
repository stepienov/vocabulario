"""Transactional mail templates (E-001/F-004/T-002)."""

import pytest

from app.services import mail_templates as mt

LINK = "https://app.example/account/reset-password#token=abc_DEF-123"


def test_every_locale_has_every_key_and_formats():
    assert set(mt.TEXTS) == set(mt.SUPPORTED_LOCALES)
    for locale, texts in mt.TEXTS.items():
        assert set(texts) == set(mt.KEYS), locale
        for mail in (
            mt.render_verify_email(locale, LINK, hours=24),
            mt.render_reset_password(locale, LINK, minutes=30),
            mt.render_password_changed(locale),
        ):
            assert mail.locale == locale
            assert mail.subject and "{" not in mail.subject + mail.text + mail.html
            assert f'lang="{locale}"' in mail.html


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("pt-rBR", "pt-BR"),
        ("pt_PT", "pt-PT"),
        ("pt", "pt-BR"),
        ("de-AT", "de"),
        ("PL", "pl"),
        ("xx", "en"),
        ("", "en"),
        (None, "en"),
    ],
)
def test_normalize_locale(raw, expected):
    assert mt.normalize_locale(raw) == expected


def test_link_and_text_are_escaped_and_rtl_is_marked():
    mail = mt.render_reset_password("ar", 'https://x.example/#token="><b>', minutes=30)
    assert 'dir="rtl"' in mail.html
    assert "<b>" not in mail.html and "&quot;&gt;&lt;b&gt;" in mail.html
    assert "30" in mail.text
    assert mail.template == f"reset_password/{mt.TEMPLATE_VERSION}"
