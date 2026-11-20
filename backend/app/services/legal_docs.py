"""Current terms/privacy versions, the manifest and the acceptance proof (E-001/F-007/T-003).

One manifest feeds the public pages, `GET /legal/current`, registration and `/me`. The proof kept
with the user is the terms version, the locale, the server time and the version of the adult
statement; no birth date, IP address or device fingerprint.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from app.core.config import get_settings
from app.core.http_errors import api_error
from app.models import User
from app.public_web.legal_texts import DOCUMENTS

TERMS_VERSION = "2026-06-01"
PRIVACY_VERSION = "2026-06-01"
ADULT_STATEMENT_VERSION = "adult-18-v1"
LEGAL_LOCALES = ("pl", "en", "es")
FALLBACK_LOCALE = "en"
KINDS = ("terms", "privacy")
_VERSIONS = {"terms": TERMS_VERSION, "privacy": PRIVACY_VERSION}

CODE_VERSION_CHANGED = "legal_version_changed"
CODE_ADULT_REQUIRED = "adult_confirmation_required"
CODE_ACCEPTANCE_REQUIRED = "terms_acceptance_required"
CODE_ACCEPTANCE_MISSING = "legal_acceptance_missing"


def resolve_locale(requested: str | None) -> str:
    """The language of the document served for a request; never a silent translation label."""
    tag = (requested or "").strip().lower().replace("_", "-").split("-")[0]
    return tag if tag in LEGAL_LOCALES else FALLBACK_LOCALE


def current_version(kind: str) -> str:
    return _VERSIONS[kind]


@lru_cache(maxsize=None)
def digest(kind: str, locale: str) -> str:
    body = json.dumps(
        [_VERSIONS[kind], DOCUMENTS[kind][locale]], ensure_ascii=False, sort_keys=True
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def document_path(kind: str, locale: str) -> str:
    return f"/documents/{kind}/{_VERSIONS[kind]}/{locale}"


def render_document(kind: str, version: str, locale: str) -> dict | None:
    """The text of one immutable version, or None for an unknown kind/version/locale."""
    if kind not in KINDS or version != _VERSIONS[kind] or locale not in LEGAL_LOCALES:
        return None
    settings = get_settings()
    values = {
        "app": "Vocabulario",
        "operator": settings.operator_name.strip() or "[operator name not configured]",
        "contact": settings.support_email.strip() or "[support e-mail not configured]",
    }
    raw = DOCUMENTS[kind][locale]
    return {
        "kind": kind,
        "version": version,
        "locale": locale,
        "title": raw["title"],
        "sections": [
            {
                "heading": heading.format(**values),
                "paragraphs": [p.format(**values) for p in paragraphs],
            }
            for heading, paragraphs in raw["sections"]
        ],
        "sha256": digest(kind, locale),
    }


def _origin() -> str:
    return get_settings().public_app_origin.strip().rstrip("/")


def manifest(requested_locale: str | None = None) -> dict:
    locale = resolve_locale(requested_locale)
    origin = _origin()
    return {
        "terms_version": TERMS_VERSION,
        "privacy_version": PRIVACY_VERSION,
        "adult_statement_version": ADULT_STATEMENT_VERSION,
        "locale": locale,
        "requested_locale": (requested_locale or "").strip()[:16] or None,
        "available_locales": list(LEGAL_LOCALES),
        "support_email": get_settings().support_email.strip() or None,
        "documents": [
            {
                "kind": kind,
                "version": _VERSIONS[kind],
                "locale": locale,
                "url": origin + document_path(kind, locale),
                "sha256": digest(kind, locale),
            }
            for kind in KINDS
        ],
    }


def manifest_etag(locale: str) -> str:
    support = get_settings().support_email.strip()
    return '"' + hashlib.sha256(
        (digest("terms", locale) + digest("privacy", locale) + support).encode("utf-8")
    ).hexdigest()[:32] + '"'


@dataclass(frozen=True)
class Acceptance:
    terms_version: str
    locale: str
    adult_confirmed: bool


def check_acceptance(acceptance: Acceptance) -> None:
    """Validate before any account exists. A stale version answers with the current manifest."""
    if acceptance.terms_version != TERMS_VERSION:
        raise api_error(
            409,
            CODE_VERSION_CHANGED,
            extra={"legal": manifest(acceptance.locale)},
        )
    if not acceptance.adult_confirmed:
        raise api_error(422, CODE_ADULT_REQUIRED)


def apply_acceptance(user: User, acceptance: Acceptance, now: datetime) -> bool:
    """Record the proof on the user; False when the same version was already accepted."""
    if is_current(user):
        return False
    user.accepted_terms_version = TERMS_VERSION
    user.accepted_privacy_version = PRIVACY_VERSION
    user.terms_locale = resolve_locale(acceptance.locale)
    user.terms_accepted_at = now
    user.adult_statement_version = ADULT_STATEMENT_VERSION
    user.adult_confirmed_at = now
    return True


def accepted_current(terms_version: str | None, adult_version: str | None, adult_at) -> bool:
    return (
        terms_version == TERMS_VERSION
        and adult_version == ADULT_STATEMENT_VERSION
        and adult_at is not None
    )


def is_current(user: User) -> bool:
    return accepted_current(
        user.accepted_terms_version, user.adult_statement_version, user.adult_confirmed_at
    )


def acceptance_required(user: User) -> bool:
    return get_settings().legal_acceptance_enforced and not is_current(user)


def legal_status(user: User) -> dict:
    return {
        "accepted_terms_version": user.accepted_terms_version,
        "required_terms_version": TERMS_VERSION,
        "adult_confirmed": user.adult_confirmed_at is not None,
        "acceptance_required": acceptance_required(user),
    }
