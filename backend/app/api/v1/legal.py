"""Public manifest of the current terms and privacy notice (E-001/F-007/T-003)."""

from fastapi import APIRouter, Query, Request, Response

from app.services import legal_docs

router = APIRouter(prefix="/legal", tags=["legal"])

_CACHE = "public, max-age=300"


@router.get("/current")
async def current_legal(
    request: Request,
    response: Response,
    locale: str | None = Query(default=None, max_length=16),
):
    resolved = legal_docs.resolve_locale(locale)
    etag = legal_docs.manifest_etag(resolved)
    headers = {"ETag": etag, "Cache-Control": _CACHE, "Vary": "Accept-Language"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return legal_docs.manifest(locale)
