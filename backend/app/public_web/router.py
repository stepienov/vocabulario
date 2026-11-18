"""Landing pages for e-mail links. GET only renders; the token is spent by an explicit POST."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.passwords import NEW_PASSWORD_MIN_CHARS, PASSWORD_MAX_CHARS
from app.public_web.texts import PAGE_TEXTS
from app.services.account_recovery import RESET_PATH, VERIFY_PATH
from app.services.email_change import CHANGE_PATH
from app.services.mail_templates import (
    APP_NAME,
    DEFAULT_LOCALE,
    RTL_LOCALES,
    normalize_locale,
)

HERE = Path(__file__).resolve().parent
ASSETS_PATH = "/account/assets"
templates = Jinja2Templates(directory=str(HERE / "templates"))
router = APIRouter(include_in_schema=False)

SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
        "img-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'"
    ),
}

_PAGES = {
    "verify": {
        "title": "verify_title",
        "intro": "verify_intro",
        "api": "/api/v1/auth/email-verification/confirm",
    },
    "reset": {
        "title": "reset_title",
        "intro": "reset_intro",
        "api": "/api/v1/auth/password-reset/confirm",
    },
    "change": {
        "title": "change_title",
        "intro": "change_intro",
        "api": "/api/v1/auth/email-change/confirm",
    },
}


def _accept_language(header: str) -> list[str]:
    """Language tags ordered by quality; malformed weights count as zero."""
    ranked: list[tuple[float, int, str]] = []
    for index, part in enumerate(header.split(",")[:20]):
        tag, _, params = part.strip().partition(";")
        tag = tag.strip()
        if not tag or tag == "*":
            continue
        quality = 1.0
        params = params.strip()
        if params.startswith("q="):
            try:
                quality = float(params[2:])
            except ValueError:
                quality = 0.0
        if quality > 0:
            ranked.append((-quality, index, tag))
    return [tag for _, _, tag in sorted(ranked)]


def page_locale(request: Request) -> str:
    """`?lang=` from the e-mail link, then the browser languages, then English."""
    explicit = request.query_params.get("lang")
    if explicit:
        return normalize_locale(explicit)
    for tag in _accept_language(request.headers.get("accept-language", "")):
        locale = normalize_locale(tag)
        if locale != DEFAULT_LOCALE or tag.lower().split("-")[0] == DEFAULT_LOCALE:
            return locale
    return DEFAULT_LOCALE


def _render(request: Request, page: str) -> HTMLResponse:
    locale = page_locale(request)
    values = {"app": APP_NAME, "min": NEW_PASSWORD_MIN_CHARS, "max": PASSWORD_MAX_CHARS}
    texts = {key: text.format(**values) for key, text in PAGE_TEXTS[locale].items()}
    spec = _PAGES[page]
    response = templates.TemplateResponse(
        request,
        "account_action.html",
        {
            "page": page,
            "locale": locale,
            "direction": "rtl" if locale in RTL_LOCALES else "ltr",
            "app_name": APP_NAME,
            "title": texts[spec["title"]],
            "intro": texts[spec["intro"]],
            "api": spec["api"],
            "texts": texts,
            "assets": ASSETS_PATH,
            "min_chars": NEW_PASSWORD_MIN_CHARS,
            "max_chars": PASSWORD_MAX_CHARS,
        },
    )
    response.headers.update(SECURITY_HEADERS)
    return response


@router.get(VERIFY_PATH, response_class=HTMLResponse)
async def verify_email_page(request: Request) -> HTMLResponse:
    return _render(request, "verify")


@router.get(RESET_PATH, response_class=HTMLResponse)
async def reset_password_page(request: Request) -> HTMLResponse:
    return _render(request, "reset")


@router.get(CHANGE_PATH, response_class=HTMLResponse)
async def change_email_page(request: Request) -> HTMLResponse:
    return _render(request, "change")


def mount_public_web(app: FastAPI) -> None:
    app.mount(ASSETS_PATH, StaticFiles(directory=str(HERE / "static")), name="account_assets")
    app.include_router(router)
