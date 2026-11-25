"""Public site: home, privacy, terms, legal index, support and Android asset links (F-007/T-004).

Pages are static text from the same manifest as `GET /api/v1/legal/current`. No cookies, scripts,
trackers, external fonts or embeds; request logs carry no query string (see AppLogMiddleware).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.core.config import get_settings
from app.public_web.alpha import ALPHA_APK, ALPHA_CERT_SHA256, ALPHA_PACKAGE
from app.public_web.router import ASSETS_PATH, SECURITY_HEADERS, page_locale, templates
from app.public_web.site_texts import SITE_TEXTS
from app.services import legal_docs
from app.services.account_deletion import deletion_enabled
from app.services.mail_templates import APP_NAME

site_router = APIRouter(include_in_schema=False)

ASSETLINKS_PATH = "/.well-known/assetlinks.json"


def _locale(request: Request) -> tuple[str, bool]:
    """The page language and whether the visitor's own language had to fall back to English."""
    wanted = page_locale(request)
    base = wanted.lower().split("-")[0]
    return legal_docs.resolve_locale(wanted), base not in legal_docs.LEGAL_LOCALES


def _render(
    request: Request,
    kind: str,
    title_key: str,
    *,
    locale: str | None = None,
    fallback: bool = False,
    **extra,
) -> HTMLResponse:
    if locale is None:
        locale, fallback = _locale(request)
    t = {key: text.format(app=APP_NAME) for key, text in SITE_TEXTS[locale].items()}
    context = {
        "kind": kind,
        "locale": locale,
        "fallback": fallback,
        "languages": legal_docs.LEGAL_LOCALES,
        "lang_links": {
            code: f"{request.url.path}?lang={code}" for code in legal_docs.LEGAL_LOCALES
        },
        "t": t,
        "app_name": APP_NAME,
        "assets": ASSETS_PATH,
        "path": request.url.path,
        "title": t.get(title_key, title_key),
        **extra,
    }
    response = templates.TemplateResponse(request, "site_page.html", context)
    response.headers.update(SECURITY_HEADERS)
    response.headers["Content-Security-Policy"] += "; font-src 'self'"
    return response


def _document_page(
    request: Request, kind: str, version: str, locale: str, *, fallback: bool = False
) -> HTMLResponse:
    document = legal_docs.render_document(kind, version, locale)
    if document is None:
        raise HTTPException(status_code=404)
    return _render(
        request,
        "document",
        "",
        locale=locale,
        fallback=fallback,
        document=document,
        title=document["title"],
        lang_links={
            code: f"/documents/{kind}/{version}/{code}" for code in legal_docs.LEGAL_LOCALES
        },
    )


@site_router.get("/", response_class=HTMLResponse)
async def home_page(request: Request) -> HTMLResponse:
    locale, _ = _locale(request)
    intro = SITE_TEXTS[locale]["home_intro"].format(app=APP_NAME)
    return _render(request, "home", "home_title", intro=intro)


@site_router.get("/download/alpha")
async def download_alpha() -> FileResponse:
    if not ALPHA_APK.is_file():
        raise HTTPException(status_code=503, detail="Alpha APK is unavailable")
    return FileResponse(
        ALPHA_APK,
        media_type="application/vnd.android.package-archive",
        filename="Vocabulario-alpha.apk",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@site_router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request) -> HTMLResponse:
    locale, fallback = _locale(request)
    version = legal_docs.current_version("privacy")
    return _document_page(request, "privacy", version, locale, fallback=fallback)


@site_router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request) -> HTMLResponse:
    locale, fallback = _locale(request)
    version = legal_docs.current_version("terms")
    return _document_page(request, "terms", version, locale, fallback=fallback)


@site_router.get("/legal", response_class=HTMLResponse)
async def legal_index_page(request: Request) -> HTMLResponse:
    locale, _ = _locale(request)
    documents = []
    for kind in legal_docs.KINDS:
        doc = legal_docs.render_document(kind, legal_docs.current_version(kind), locale)
        documents.append({**doc, "path": legal_docs.document_path(kind, locale)})
    intro = SITE_TEXTS[locale]["legal_intro"].format(app=APP_NAME)
    return _render(request, "legal", "legal_title", documents=documents, intro=intro)


@site_router.get("/support", response_class=HTMLResponse)
async def support_page(request: Request) -> HTMLResponse:
    locale, _ = _locale(request)
    texts = SITE_TEXTS[locale]
    contact = get_settings().support_email.strip() or texts["not_configured"]
    return _render(
        request, "support", "support_title", intro=texts["support_intro"], contact=contact,
        deletion_enabled=deletion_enabled(),
    )


@site_router.get("/documents/{kind}/{version}/{locale}", response_class=HTMLResponse)
async def document_page(request: Request, kind: str, version: str, locale: str) -> HTMLResponse:
    return _document_page(request, kind, version, locale)


@site_router.get(ASSETLINKS_PATH)
async def assetlinks() -> JSONResponse:
    settings = get_settings()
    prints = [p.strip().upper() for p in settings.android_cert_sha256.split(",") if p.strip()]
    body = []
    if prints:
        body = [
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": settings.android_package,
                    "sha256_cert_fingerprints": prints,
                },
            }
        ]
    if ALPHA_APK.is_file():
        body.append(
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": ALPHA_PACKAGE,
                    "sha256_cert_fingerprints": [ALPHA_CERT_SHA256],
                },
            }
        )
    return JSONResponse(body, headers={"Cache-Control": "public, max-age=3600"})
