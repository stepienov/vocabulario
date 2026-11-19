"""Content reports API (E-001/F-007/T-002)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_verified_user
from app.core.http_errors import api_error
from app.db.session import get_db
from app.models import User
from app.schemas.content_reports import ContentReportCreate, ContentReportResponse
from app.services import content_reports as service
from app.services.auth_limits import MIN, Rule, client_ip, enforce

router = APIRouter(prefix="/content-reports", tags=["content-reports"])


def _response(outcome: service.ReportOutcome) -> ContentReportResponse:
    return ContentReportResponse(
        report_id=outcome.report_id,
        status=outcome.status,
        received_at=outcome.received_at,
        resolution_code=outcome.resolution_code,
    )


@router.post("", response_model=ContentReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    body: ContentReportCreate,
    request: Request,
    response: Response,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> ContentReportResponse:
    # Own scope: reports must stay possible when study traffic is limited, and vice versa.
    await enforce(
        Rule("content_report_user", str(user.id), 10, MIN),
        Rule("content_report_ip", client_ip(request), 30, MIN),
    )
    outcome = await service.submit_report(db, user, body)
    response.headers["Cache-Control"] = "no-store"
    if not outcome.created:
        response.status_code = status.HTTP_200_OK
    return _response(outcome)


@router.get("/{report_id}", response_model=ContentReportResponse)
async def get_report(
    report_id: UUID,
    response: Response,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> ContentReportResponse:
    outcome = await service.owner_view(db, user.id, report_id)
    if outcome is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "report_not_found")
    response.headers["Cache-Control"] = "no-store"
    return _response(outcome)
