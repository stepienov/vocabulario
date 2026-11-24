from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.admin_ui import queries as q
from app.admin_ui.auth import (
    LoginRequired,
    PanelDisabled,
    clear_session_cookie,
    panel_enabled,
    require_panel,
    set_session_cookie,
    verify_credentials,
)
from app.admin_ui.helpers import (
    NAV,
    fmt_dt,
    fmt_int,
    fmt_usd,
    parse_dt,
    qs,
    status_label,
    status_tone,
)
from app.db.session import get_db
from app.models import LearningCard

HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
templates.env.filters["dt"] = fmt_dt
templates.env.filters["usd"] = fmt_usd
templates.env.filters["intsp"] = fmt_int
templates.env.filters["status"] = status_label
templates.env.filters["tone"] = status_tone
templates.env.filters["tojson"] = lambda v: json.dumps(v, ensure_ascii=False, indent=2, default=str)

router = APIRouter(prefix="/admin", include_in_schema=False)
static_router = APIRouter(include_in_schema=False)


def _ctx(request: Request, nav: str, title: str, **extra: Any) -> dict[str, Any]:
    return {
        "request": request,
        "nav": nav,
        "title": title,
        "nav_items": NAV,
        "qs": lambda **u: qs(request, **u),
        **extra,
    }


def _page(raw: int | None) -> int:
    return max(1, int(raw or 1))


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, next: str = "/admin", error: str | None = None):
    if not panel_enabled():
        raise PanelDisabled()
    return templates.TemplateResponse(
        request,
        "login.html",
        {"title": "Logowanie", "next": next, "error": error},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/admin"),
):
    if not panel_enabled():
        raise PanelDisabled()
    if not verify_credentials(username, password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"title": "Logowanie", "next": next, "error": "Nieprawidłowy login lub hasło."},
            status_code=401,
        )
    target = next if next.startswith("/admin") else "/admin"
    response = RedirectResponse(target, status_code=303)
    set_session_cookie(response, username)
    return response


@router.post("/logout")
async def logout():
    response = RedirectResponse("/admin/login", status_code=303)
    clear_session_cookie(response)
    return response


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def overview(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
):
    kpis = await q.overview_kpis(db)
    return templates.TemplateResponse(
        request, "overview.html", _ctx(request, "overview", "Przegląd", **kpis)
    )


@router.get("/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
    q_text: str | None = Query(None, alias="q"),
    page: int = 1,
):
    rows, total = await q.list_users(db, q=q_text, page=_page(page))
    return templates.TemplateResponse(
        request,
        "users.html",
        _ctx(request, "users", "Użytkownicy", rows=rows, total=total, page=_page(page), q=q_text or ""),
    )


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def user_page(
    request: Request,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
):
    data = await q.user_detail(db, user_id)
    if data is None:
        raise StarletteHTTPException(404, "Nie znaleziono użytkownika")
    return templates.TemplateResponse(
        request, "user_detail.html", _ctx(request, "users", data["user"].email, **data)
    )


@router.get("/lists", response_class=HTMLResponse)
async def lists_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
    q_text: str | None = Query(None, alias="q"),
    page: int = 1,
):
    rows, total = await q.list_word_lists(db, q=q_text, page=_page(page))
    return templates.TemplateResponse(
        request,
        "lists.html",
        _ctx(request, "lists", "Listy", rows=rows, total=total, page=_page(page), q=q_text or ""),
    )


@router.get("/lists/{list_id}", response_class=HTMLResponse)
async def list_page(
    request: Request,
    list_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
):
    data = await q.list_detail(db, list_id)
    if data is None:
        raise StarletteHTTPException(404, "Nie znaleziono listy")
    return templates.TemplateResponse(
        request, "list_detail.html", _ctx(request, "lists", data["list"].name, **data)
    )


@router.get("/cards", response_class=HTMLResponse)
async def cards_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
    q_text: str | None = Query(None, alias="q"),
    status: str | None = None,
    page: int = 1,
):
    rows, total = await q.list_cards(db, q=q_text, status=status, user_id=None, page=_page(page))
    return templates.TemplateResponse(
        request,
        "cards.html",
        _ctx(
            request,
            "cards",
            "Słowa",
            rows=rows,
            total=total,
            page=_page(page),
            q=q_text or "",
            status=status or "",
        ),
    )


@router.get("/cards/{card_id}", response_class=HTMLResponse)
async def card_page(
    request: Request,
    card_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
):
    data = await q.card_detail(db, card_id)
    if data is None:
        raise StarletteHTTPException(404, "Nie znaleziono karty")
    if data["entry"] is not None:
        from app.services.shared_content import content_revision

        data["content_revision"] = content_revision(data["entry"].content)
    return templates.TemplateResponse(
        request,
        "card_detail.html",
        _ctx(request, "cards", data["card"].lemma_l2, **data),
    )


@router.get("/llm-usage/{usage_id}", response_class=HTMLResponse)
async def llm_usage_payload_page(
    request: Request,
    usage_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
):
    data = await q.llm_usage_payload(db, usage_id)
    if data is None:
        raise StarletteHTTPException(404, "Nie znaleziono wołania LLM")
    return templates.TemplateResponse(
        request,
        "llm_usage_payload.html",
        _ctx(request, "costs", data["usage"].purpose, **data),
    )


@router.post("/cards/{card_id}/retry-enrichment")
async def retry_enrichment(
    card_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
):
    card = await q.admin_retry_enrichment(db, card_id)
    if card is None:
        raise StarletteHTTPException(404, "Nie znaleziono karty")
    return RedirectResponse(f"/admin/cards/{card_id}", status_code=303)


@router.post("/cards/{card_id}/publish-content")
async def publish_card_content(
    card_id: UUID,
    content_json: str = Form(...),
    expected_generation: int = Form(...),
    expected_content_revision: str = Form(...),
    learning_impact: bool = Form(...),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
):
    card = await db.get(LearningCard, card_id)
    if card is None:
        raise StarletteHTTPException(404, "Nie znaleziono karty")
    if card.lexical_entry_id is None:
        raise StarletteHTTPException(409, "Karta nie ma wspólnego wpisu leksykalnego")
    try:
        content = json.loads(content_json)
    except json.JSONDecodeError as exc:
        raise StarletteHTTPException(422, "Treść musi być poprawnym JSON-em") from exc
    if not isinstance(content, dict):
        raise StarletteHTTPException(422, "Treść musi być obiektem JSON")

    from app.services.shared_content import publish_lexical_content

    try:
        await publish_lexical_content(
            db,
            entry_id=card.lexical_entry_id,
            expected_generation=expected_generation,
            expected_content_revision=expected_content_revision,
            content=content,
            learning_impact=learning_impact,
        )
    except ValueError as exc:
        await db.rollback()
        message = {
            "unmigrated_card_content": "Najpierw rozstrzygnij i przenieś wcześniejsze kopie treści tej karty",
            "content_revision_conflict": "Treść zmieniła się podczas edycji; otwórz ją ponownie",
            "content_generation_conflict": "Generacja nauki zmieniła się podczas edycji",
            "content_identity_conflict": "Nie można zmienić tożsamości słowa ani pary języków",
            "incomplete_shared_content": "Wspólna treść musi być kompletna i zawierać przykłady",
            "family_edit_requires_reconciliation": "Zmiana rodziny wyrazów wymaga osobnego uzgodnienia",
        }.get(str(exc), "Nie można opublikować treści lub decyzja o resecie jest niespójna")
        raise StarletteHTTPException(409, message) from exc
    except LookupError as exc:
        await db.rollback()
        raise StarletteHTTPException(404, "Nie znaleziono wpisu leksykalnego") from exc
    except IntegrityError as exc:
        await db.rollback()
        raise StarletteHTTPException(409, "Poprawione hasło koliduje z istniejącą kartą lub wpisem") from exc
    await db.commit()
    return RedirectResponse(f"/admin/cards/{card_id}", status_code=303)


@router.post("/escalations/{escalation_id}/done")
async def mark_escalation_done_page(
    escalation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
):
    from app.services.card_corrections import mark_escalation_done

    row = await mark_escalation_done(db, escalation_id)
    if row is None:
        raise StarletteHTTPException(404, "Nie znaleziono zgłoszenia")
    await db.commit()
    return RedirectResponse("/admin/errors?tab=qa", status_code=303)


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
    status: str = "",
    page: int = 1,
):
    from app.core.security import now_utc
    from app.services import content_reports as reports

    rows, total = await reports.list_reports(db, status=status or None, page=_page(page))
    now = now_utc()
    items = [
        {
            "r": r,
            "overdue": r.status != "resolved"
            and reports.working_days_between(r.received_at, now)
            > reports.RESPONSE_TARGET_WORKING_DAYS,
        }
        for r in rows
    ]
    return templates.TemplateResponse(
        request,
        "reports.html",
        _ctx(
            request,
            "reports",
            "Zgłoszenia treści",
            items=items,
            total=total,
            page=_page(page),
            status=status,
            codes=reports.RESOLUTION_CODES,
        ),
    )


@router.post("/reports/{report_id}/take")
async def report_take(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_panel),
):
    from app.services import content_reports as reports

    if not await reports.take_report(db, report_id, admin):
        raise StarletteHTTPException(409, "Zgłoszenie nie jest w statusie „przyjęte”")
    await db.commit()
    return RedirectResponse("/admin/reports", status_code=303)


@router.post("/reports/{report_id}/resolve")
async def report_resolve(
    report_id: UUID,
    code: str = Form(...),
    note: str = Form(""),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_panel),
):
    from app.services import content_reports as reports

    if code not in reports.RESOLUTION_CODES:
        raise StarletteHTTPException(422, "Nieznany kod rozwiązania")
    if not await reports.resolve_report(db, report_id, admin, code, note):
        raise StarletteHTTPException(409, "Zgłoszenie nie jest w statusie „w analizie”")
    await db.commit()
    return RedirectResponse("/admin/reports", status_code=303)


@router.get("/lookups", response_class=HTMLResponse)
async def lookups_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
    q_text: str | None = Query(None, alias="q"),
    tab: str = "events",
    page: int = 1,
):
    page_n = _page(page)
    events, events_total = await q.list_lookup_events(db, q=q_text, user_id=None, page=page_n)
    cache, cache_total = await q.list_lookup_cache(db, q=q_text, page=page_n)
    return templates.TemplateResponse(
        request,
        "lookups.html",
        _ctx(
            request,
            "lookups",
            "Wyszukiwania",
            tab=tab,
            q=q_text or "",
            page=page_n,
            events=events,
            events_total=events_total,
            cache=cache,
            cache_total=cache_total,
        ),
    )


@router.get("/reviews", response_class=HTMLResponse)
async def reviews_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
    q_text: str | None = Query(None, alias="q"),
    page: int = 1,
):
    rows, total = await q.list_reviews(db, q=q_text, page=_page(page))
    return templates.TemplateResponse(
        request,
        "reviews.html",
        _ctx(request, "reviews", "Powtórki", rows=rows, total=total, page=_page(page), q=q_text or ""),
    )


@router.get("/costs", response_class=HTMLResponse)
async def costs_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
    q_text: str | None = Query(None, alias="q"),
    purpose: str | None = None,
    operation_kind: str | None = None,
    status: str | None = None,
    group: str = "purpose",
    page: int = 1,
):
    kwargs = {
        "q": q_text,
        "user_id": None,
        "purpose": purpose,
        "operation_kind": operation_kind,
        "status": status,
        "model": None,
        "since": parse_dt(request.query_params.get("from")),
        "until": parse_dt(request.query_params.get("to")),
        "operation_id": None,
        "card_id": None,
    }
    rows, total, summary = await q.list_llm_usage(db, page=_page(page), **kwargs)
    grouped = await q.llm_usage_grouped(db, group, **kwargs)
    return templates.TemplateResponse(
        request,
        "costs.html",
        _ctx(
            request,
            "costs",
            "Koszty LLM",
            rows=rows,
            total=total,
            summary=summary,
            grouped=grouped,
            group=group,
            page=_page(page),
            q=q_text or "",
            purpose=purpose or "",
            operation_kind=operation_kind or "",
            status=status or "",
        ),
    )


@router.get("/errors", response_class=HTMLResponse)
async def errors_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
    q_text: str | None = Query(None, alias="q"),
    level: str | None = None,
    tab: str = "logs",
    page: int = 1,
):
    logs, logs_total = await q.list_errors(db, q=q_text, level=level, page=_page(page))
    failed, failed_total = await q.failed_cards(db, _page(page))
    qa, qa_total = await q.content_reviews(db, _page(page))
    return templates.TemplateResponse(
        request,
        "errors.html",
        _ctx(
            request,
            "errors",
            "Błędy",
            tab=tab,
            q=q_text or "",
            level=level or "",
            page=_page(page),
            logs=logs,
            logs_total=logs_total,
            failed=failed,
            failed_total=failed_total,
            qa=qa,
            qa_total=qa_total,
        ),
    )


@router.get("/imports", response_class=HTMLResponse)
async def imports_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
    q_text: str | None = Query(None, alias="q"),
    status: str | None = None,
    page: int = 1,
):
    rows, total = await q.list_imports(db, q=q_text, status=status, page=_page(page))
    return templates.TemplateResponse(
        request,
        "imports.html",
        _ctx(
            request,
            "imports",
            "Importy",
            rows=rows,
            total=total,
            page=_page(page),
            q=q_text or "",
            status=status or "",
        ),
    )


@router.get("/imports/{job_id}", response_class=HTMLResponse)
async def import_page(
    request: Request,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_panel),
):
    data = await q.import_detail(db, job_id)
    if data is None:
        raise StarletteHTTPException(404, "Nie znaleziono importu")
    title = data["job"].source_name or str(data["job"].id)
    return templates.TemplateResponse(
        request, "import_detail.html", _ctx(request, "imports", title, **data)
    )


def mount_admin(app) -> None:
    static_dir = HERE / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/admin/static", StaticFiles(directory=str(static_dir)), name="admin_static")
    app.include_router(router)

    @app.exception_handler(LoginRequired)
    async def _login_required(_request: Request, exc: LoginRequired):
        return RedirectResponse(f"/admin/login?next={exc.next_url}", status_code=303)

    @app.exception_handler(PanelDisabled)
    async def _panel_disabled(_request: Request, _exc: PanelDisabled):
        return JSONResponse({"detail": "Not found"}, status_code=404)
