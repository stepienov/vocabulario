"""Public account deletion routes (E-001/F-006/T-002).

Public does not mean unprotected: every call is rate limited and every mutation needs a
dedicated one-use proof. No route here issues access or refresh tokens.
"""

import logging

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http_errors import api_error
from app.core.security import now_utc
from app.db.session import get_db
from app.models import AccountDeletion
from app.schemas import MailAcceptedResponse
from app.schemas.account_deletion import (
    DeletionCancelBody,
    DeletionCancelResponse,
    DeletionEmailRequest,
    DeletionPasswordProofRequest,
    DeletionProofResponse,
    DeletionRequestBody,
    DeletionStatusRequest,
    DeletionView,
)
from app.services.account_deletion import (
    can_cancel,
    cancel_deletion,
    deletion_status,
    password_proof,
    request_deletion,
    request_email_proof,
    token_error,
)
from app.services.account_errors import CredentialError
from app.services.account_recovery import RETRY_AFTER_SECONDS, ensure_mail_available
from app.services.action_tokens import (
    CANCEL_DELETION,
    REQUEST_DELETION,
    ActionTokenError,
    find_token_owner,
)
from app.services.auth_limits import (
    MIN,
    LimiterUnavailable,
    RateLimited,
    Rule,
    client_ip,
    enforce,
    reserve,
)
from app.services.mail_outbox import wake_mail_worker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account-deletion", tags=["account-deletion"])


def _public(ip: str) -> Rule:
    return Rule("auth_public_ip", ip, 120, 15 * MIN)


def _error(exc: CredentialError) -> Exception:
    return api_error(exc.status_code, exc.code)


async def _fail(db: AsyncSession, exc: CredentialError) -> Exception:
    await db.rollback()
    return _error(exc)


def _view(deletion: AccountDeletion) -> DeletionView:
    now = now_utc()
    return DeletionView(
        deletion_id=deletion.id,
        state=deletion.state,
        requested_at=deletion.requested_at,
        cancel_until=deletion.cancel_until,
        purge_due_at=deletion.purge_due_at,
        can_cancel=can_cancel(deletion, now),
        cancelled_at=deletion.cancelled_at,
        completed_at=deletion.completed_at,
        server_time=now,
    )


async def _mutation_budget(db: AsyncSession, token: str, purpose: str, action: str) -> None:
    """3 new mutations per hour and owner; an exact retry never reaches this."""
    try:
        owner = await find_token_owner(db, token, purpose)
    except ActionTokenError as exc:
        raise _error(token_error(exc)) from exc
    await enforce(Rule(f"account_deletion_{action}", str(owner), 3, 60 * MIN))


@router.post("/proof/password", response_model=DeletionProofResponse)
async def proof_password(
    body: DeletionPasswordProofRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> DeletionProofResponse:
    ip = client_ip(request)
    email = str(body.email).lower()
    await enforce(
        _public(ip),
        Rule("account_deletion_proof_ip", ip, 20, 15 * MIN),
        Rule("account_deletion_proof_pair", f"{ip}|{email}", 5, 5 * MIN),
    )
    try:
        proof = await password_proof(db, email, body.password, body.action)
    except CredentialError as exc:
        raise await _fail(db, exc) from exc
    result = DeletionProofResponse(
        action_token=proof.token,
        action=proof.action,
        method=proof.method,
        expires_at=proof.expires_at,
        user_id=proof.user_id,
        deletion_id=proof.deletion_id,
        state=proof.state,
    )
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/email/request",
    response_model=MailAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def email_request(
    body: DeletionEmailRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> MailAcceptedResponse:
    """Same answer for every address; a real link only for a verified, eligible account."""
    ip = client_ip(request)
    await enforce(_public(ip), Rule("account_deletion_mail_ip", ip, 20, 15 * MIN))
    try:
        await ensure_mail_available()
    except CredentialError as exc:
        raise _error(exc) from exc
    address = str(body.email).lower()
    try:
        await reserve(
            Rule("mail_deletion_addr_cooldown", f"{address}|{body.action}", 1, MIN),
            Rule("mail_deletion_addr_hour", f"{address}|{body.action}", 3, 60 * MIN),
            now=now_utc(),
        )
    except RateLimited:
        return MailAcceptedResponse(retry_after_seconds=RETRY_AFTER_SECONDS)
    except LimiterUnavailable as exc:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_temporarily_unavailable") from exc
    queued = await request_email_proof(db, address, body.action, None)
    await db.commit()
    if queued:
        wake_mail_worker()
    return MailAcceptedResponse(retry_after_seconds=RETRY_AFTER_SECONDS)


@router.post("/request", response_model=DeletionView, status_code=status.HTTP_202_ACCEPTED)
async def request_account_deletion(
    body: DeletionRequestBody, request: Request, db: AsyncSession = Depends(get_db)
) -> DeletionView:
    await enforce(_public(client_ip(request)))
    known = await db.get(AccountDeletion, body.request_id)
    if known is None:
        await _mutation_budget(db, body.action_token, REQUEST_DELETION, "request")
    try:
        deletion = await request_deletion(
            db,
            body.action_token,
            body.request_id,
            body.status_secret,
            body.confirmation_version,
        )
    except CredentialError as exc:
        raise await _fail(db, exc) from exc
    result = _view(deletion)
    await db.commit()
    wake_mail_worker()
    return result


@router.post("/status", response_model=DeletionView)
async def status_of_deletion(
    body: DeletionStatusRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> DeletionView:
    ip = client_ip(request)
    await enforce(_public(ip), Rule("account_deletion_status_ip", ip, 60, 15 * MIN))
    try:
        deletion = await deletion_status(
            db,
            request_id=body.request_id,
            status_secret=body.status_secret,
            action_token=body.action_token,
        )
    except CredentialError as exc:
        raise await _fail(db, exc) from exc
    response.headers["Cache-Control"] = "no-store"
    return _view(deletion)


@router.post("/cancel", response_model=DeletionCancelResponse)
async def cancel_account_deletion(
    body: DeletionCancelBody,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> DeletionCancelResponse:
    await enforce(_public(client_ip(request)))
    known = await db.get(AccountDeletion, body.deletion_id)
    if known is None or known.cancel_request_id != body.request_id:
        await _mutation_budget(db, body.action_token, CANCEL_DELETION, "cancel")
    try:
        deletion = await cancel_deletion(
            db, body.action_token, body.deletion_id, body.request_id
        )
    except CredentialError as exc:
        raise await _fail(db, exc) from exc
    result = DeletionCancelResponse(deletion=_view(deletion))
    await db.commit()
    wake_mail_worker()
    response.headers["Cache-Control"] = "no-store"
    return result
