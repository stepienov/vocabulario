"""Landing pages for e-mail links. GET only renders; the token is spent by an explicit POST."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.core.passwords import NEW_PASSWORD_MIN_CHARS, PASSWORD_MAX_CHARS
from app.public_web.texts import PAGE_TEXTS
from app.services.account_deletion import CANCEL_PATH, REQUEST_PATH, deletion_enabled
from app.services.account_recovery import RESET_PATH, VERIFY_PATH
from app.services.mail_templates import (
    APP_NAME,
    DEFAULT_LOCALE,
    RTL_LOCALES,
    normalize_locale,
)

HERE = Path(__file__).resolve().parent
ASSETS_PATH = "/account/assets"
START_PATH = "/delete-account"
STATUS_PATH = "/account/deletion-status"
DELETION_API = "/api/v1/account-deletion"
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
    "delete_start": {
        "title": "del_title",
        "intro": "del_intro",
        "api": DELETION_API,
        "template": "account_deletion.html",
    },
    "delete_confirm": {
        "title": "del_title",
        "intro": "del_intro",
        "api": DELETION_API,
        "template": "account_deletion.html",
    },
    "delete_cancel": {
        "title": "del_cancel_title",
        "intro": "del_cancel_intro",
        "api": DELETION_API,
        "template": "account_deletion.html",
    },
    "delete_status": {
        "title": "del_status_title",
        "intro": "del_status_intro",
        "api": DELETION_API,
        "template": "account_deletion.html",
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
        spec.get("template", "account_action.html"),
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
            "google_client_id": get_settings().google_oauth_client_id if page == "delete_start" else "",
            "deletion_enabled": deletion_enabled() if page == "delete_start" else True,
        },
    )
    response.headers.update(SECURITY_HEADERS)
    if page == "delete_start" and get_settings().google_oauth_client_id:
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self' https://accounts.google.com/gsi/client; "
            "style-src 'self' https://accounts.google.com/gsi/style; "
            "connect-src 'self' https://accounts.google.com/gsi/; "
            "frame-src https://accounts.google.com/gsi/; img-src 'self'; "
            "form-action 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    return response


@router.get(VERIFY_PATH, response_class=HTMLResponse)
async def verify_email_page(request: Request) -> HTMLResponse:
    return _render(request, "verify")


@router.get(RESET_PATH, response_class=HTMLResponse)
async def reset_password_page(request: Request) -> HTMLResponse:
    return _render(request, "reset")


@router.get(START_PATH, response_class=HTMLResponse)
async def delete_account_start_page(request: Request) -> HTMLResponse:
    return _render(request, "delete_start")


@router.get(REQUEST_PATH, response_class=HTMLResponse)
async def delete_account_confirm_page(request: Request) -> HTMLResponse:
    return _render(request, "delete_confirm")


@router.get(CANCEL_PATH, response_class=HTMLResponse)
async def cancel_deletion_page(request: Request) -> HTMLResponse:
    return _render(request, "delete_cancel")


@router.get(STATUS_PATH, response_class=HTMLResponse)
async def deletion_status_page(request: Request) -> HTMLResponse:
    return _render(request, "delete_status")


def mount_public_web(app: FastAPI) -> None:
    from app.public_web.site import site_router

    app.mount(ASSETS_PATH, StaticFiles(directory=str(HERE / "static")), name="account_assets")
    app.include_router(router)
    app.include_router(site_router)
