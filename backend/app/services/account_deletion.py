"""Account deletion process: proofs, request, cancel and status (E-001/F-006/T-002).

Helpers run in the caller's transaction and never commit; the caller commits and then wakes
the mail worker. Lock order: user -> sessions -> recent proofs -> email change -> deletion
-> action tokens -> mail buckets -> outbox. Nothing here mutates on a read-only check.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.passwords import dummy_verify, verify_current_password
from app.core.security import now_utc
from app.models import (
    AccountActionToken,
    AccountDeletion,
    AccountEmailChange,
    RecentAuthProof,
    User,
)
from app.services.account_errors import CredentialError
from app.services.account_recovery import (
    NOTICE_TTL,
    account_link,
    next_mail_allowed_at,
    profile_locale,
    queue_account_mail,
)
from app.services.action_tokens import (
    CANCEL_DELETION,
    REQUEST_DELETION,
    TOKEN_TTL,
    ActionTokenError,
    consume_action_token,
    find_token_owner,
    issue_action_token,
    peek_action_token,
)
from app.services.auth_sessions import lock_user, revoke_user_sessions
from app.services.mail_templates import (
    normalize_locale,
    render_cancel_account_deletion,
    render_deletion_cancelled,
    render_deletion_started,
    render_request_account_deletion,
)

CANCEL_WINDOW = timedelta(hours=168)
PURGE_DEADLINE = timedelta(days=14)
PROOF_TTL = timedelta(minutes=5)
STARTED_KIND = "account_deletion_started"
CANCELLED_KIND = "account_deletion_cancelled"
REQUEST_PATH = "/account/delete-account"
CANCEL_PATH = "/account/cancel-deletion"
PURPOSE = {"request": REQUEST_DELETION, "cancel": CANCEL_DELETION}
ACTIVE_STATES = ("grace", "purging")


@dataclass(frozen=True)
class DeletionProof:
    token: str
    action: str
    method: str
    expires_at: datetime
    user_id: UUID
    deletion_id: UUID | None
    state: str | None


def secret_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("ascii")).hexdigest()


def subject_hmac(user_id: UUID) -> tuple[str, int]:
    """Keyed pseudonym of the user id that outlives the row; the key never leaves settings."""
    settings = get_settings()
    digest = hmac.new(
        settings.account_erasure_key.strip().encode("utf-8"),
        f"account-deletion:{user_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return digest, settings.account_erasure_key_version


def deletion_enabled() -> bool:
    settings = get_settings()
    return settings.account_deletion_enabled and settings.erasure_key_ready()


def _unavailable() -> CredentialError:
    return CredentialError(503, "account_deletion_unavailable")


def _action_required() -> CredentialError:
    return CredentialError(403, "account_action_required")


def token_error(exc: ActionTokenError) -> CredentialError:
    """Deletion proofs answer with their own codes: unusable -> required, expired -> expired."""
    if exc.status_code == 410:
        return CredentialError(410, "account_action_expired")
    return _action_required()


def _fingerprint(status_secret: str, version: str) -> str:
    return hashlib.sha256(f"{version}\n{status_secret}".encode()).hexdigest()


def _cancel_fingerprint(deletion_id: UUID, request_id: UUID) -> str:
    return hashlib.sha256(f"cancel\n{deletion_id}\n{request_id}".encode()).hexdigest()


def can_cancel(deletion: AccountDeletion, now: datetime) -> bool:
    return deletion.state == "grace" and now < deletion.cancel_until


async def _active_process(
    db: AsyncSession, user_id: UUID, *, lock: bool = True
) -> AccountDeletion | None:
    query = select(AccountDeletion).where(
        AccountDeletion.user_id == user_id, AccountDeletion.state.in_(ACTIVE_STATES)
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return (await db.execute(query)).scalar_one_or_none()


async def _issue_proof(
    db: AsyncSession,
    user: User,
    action: str,
    method: str,
    *,
    ttl: timedelta,
    now: datetime,
) -> tuple[DeletionProof | None, AccountDeletion | None]:
    """Proof for a locked, already identified owner; None when the action does not apply."""
    process = await _active_process(db, user.id)
    target = None
    if action == "request":
        if user.account_status == "deleting" or (process and process.state != "grace"):
            raise CredentialError(409, "deletion_irreversible")
        if not deletion_enabled():
            raise _unavailable()
        expires = now + ttl
    else:
        if process is None:
            raise CredentialError(409, "no_pending_deletion")
        if not can_cancel(process, now):
            raise CredentialError(409, "deletion_irreversible")
        target = process.id
        expires = min(now + ttl, process.cancel_until)
    issued = await issue_action_token(
        db,
        user,
        PURPOSE[action],
        now=now,
        expires_at=expires,
        proof_method=method,
        target_deletion_id=target,
    )
    proof = DeletionProof(
        token=issued.token,
        action=action,
        method=method,
        expires_at=issued.row.expires_at,
        user_id=user.id,
        deletion_id=process.id if process else None,
        state=process.state if process else None,
    )
    return proof, process


async def password_proof(
    db: AsyncSession, email: str, password: str, action: str, *, now: datetime | None = None
) -> DeletionProof:
    """Same work and neutral answer as a login; no session is created."""
    now = now or now_utc()
    user = (
        await db.execute(select(User).where(User.email == email.lower()))
    ).scalar_one_or_none()
    stored = user.password_hash if user else None
    if not stored:
        await dummy_verify(password)
        raise CredentialError(401, "invalid_credentials")
    if not await verify_current_password(password, stored):
        raise CredentialError(401, "invalid_credentials")
    locked = await lock_user(db, user.id)
    if locked is None or locked.password_hash != stored:
        raise CredentialError(401, "invalid_credentials")
    proof, _ = await _issue_proof(db, locked, action, "password", ttl=PROOF_TTL, now=now)
    return proof


async def request_email_proof(
    db: AsyncSession, email: str, action: str, locale: str | None, *, now: datetime | None = None
) -> bool:
    """Queue a proof link for a verified address; the caller always answers the same way."""
    now = now or now_utc()
    user_id = (
        await db.execute(
            select(User.id).where(
                User.email == email.lower(), User.email_verified_at.is_not(None)
            )
        )
    ).scalar_one_or_none()
    if user_id is None:
        return False
    user = await lock_user(db, user_id)
    if user is None or user.email_verified_at is None:
        return False
    purpose = PURPOSE[action]
    if await next_mail_allowed_at(db, user.id, purpose, now) is not None:
        return False
    try:
        proof, _ = await _issue_proof(
            db, user, action, "email", ttl=TOKEN_TTL[purpose], now=now
        )
    except CredentialError:
        return False
    row = (
        await db.execute(
            select(AccountActionToken).where(
                AccountActionToken.token_hash
                == hashlib.sha256(proof.token.encode("utf-8")).hexdigest()
            )
        )
    ).scalar_one()
    mail_locale = normalize_locale(locale or await profile_locale(db, user.id))
    minutes = int((row.expires_at - now).total_seconds() // 60)
    if minutes < 1:
        return False
    link = account_link(
        REQUEST_PATH if action == "request" else CANCEL_PATH, proof.token, mail_locale
    )
    render = render_request_account_deletion if action == "request" else render_cancel_account_deletion
    await queue_account_mail(
        db,
        user,
        purpose,
        render(mail_locale, link, minutes=minutes),
        expires_at=row.expires_at,
        now=now,
        action_token_id=row.id,
    )
    return True


async def _invalidate_user_proofs(db: AsyncSession, user_id: UUID, now: datetime) -> None:
    await db.execute(
        update(RecentAuthProof)
        .where(RecentAuthProof.user_id == user_id, RecentAuthProof.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    await db.execute(
        update(AccountEmailChange)
        .where(AccountEmailChange.user_id == user_id, AccountEmailChange.state == "pending")
        .values(state="cancelled", finished_at=now)
    )
    await db.execute(
        update(AccountActionToken)
        .where(
            AccountActionToken.user_id == user_id,
            AccountActionToken.consumed_at.is_(None),
            AccountActionToken.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )


def _public_url(path: str, locale: str) -> str:
    origin = get_settings().public_app_origin.strip().rstrip("/") or "http://localhost:8000"
    return f"{origin}{path}?lang={locale}"


async def request_deletion(
    db: AsyncSession,
    token: str,
    request_id: UUID,
    status_secret: str,
    version: str,
    *,
    now: datetime | None = None,
) -> AccountDeletion:
    now = now or now_utc()
    try:
        owner_id = await find_token_owner(db, token, REQUEST_DELETION)
    except ActionTokenError as exc:
        raise token_error(exc) from exc
    user = await lock_user(db, owner_id)
    if user is None:
        raise _action_required()
    fingerprint = _fingerprint(status_secret, version)
    existing = (
        await db.execute(
            select(AccountDeletion)
            .where(AccountDeletion.id == request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if existing is not None:
        if (
            existing.user_id != user.id
            or existing.request_fingerprint != fingerprint
            or not hmac.compare_digest(existing.status_secret_hash, secret_hash(status_secret))
        ):
            raise CredentialError(409, "operation_id_conflict")
        return existing
    active = await _active_process(db, user.id)
    try:
        if active is not None:
            await peek_action_token(db, user, token, REQUEST_DELETION, now=now)
            return active
        if not deletion_enabled():
            raise _unavailable()
        if user.account_status != "active":
            raise CredentialError(409, "deletion_irreversible")
        await consume_action_token(db, user, token, REQUEST_DELETION, now=now)
    except ActionTokenError as exc:
        raise token_error(exc) from exc
    hmac_value, key_version = subject_hmac(user.id)
    deletion = AccountDeletion(
        id=request_id,
        user_id=user.id,
        subject_hmac=hmac_value,
        subject_key_version=key_version,
        state="grace",
        requested_at=now,
        cancel_until=now + CANCEL_WINDOW,
        purge_due_at=now + PURGE_DEADLINE,
        status_secret_hash=secret_hash(status_secret),
        request_fingerprint=fingerprint,
        stage="grace",
        attempts=0,
    )
    db.add(deletion)
    user.account_status = "deletion_pending"
    user.lifecycle_revision = user.lifecycle_revision + 1
    await db.flush()
    await revoke_user_sessions(db, user.id, "account_deleted", now=now)
    await _invalidate_user_proofs(db, user.id, now)
    if user.email_verified_at is not None:
        locale = normalize_locale(await profile_locale(db, user.id))
        rendered = render_deletion_started(
            locale,
            date=deletion.cancel_until.strftime("%Y-%m-%d %H:%M"),
            url=_public_url(CANCEL_PATH, locale),
        )
        await queue_account_mail(
            db, user, STARTED_KIND, rendered, expires_at=now + NOTICE_TTL, now=now
        )
    return deletion


async def cancel_deletion(
    db: AsyncSession,
    token: str,
    deletion_id: UUID,
    request_id: UUID,
    *,
    now: datetime | None = None,
) -> AccountDeletion:
    now = now or now_utc()
    try:
        owner_id = await find_token_owner(db, token, CANCEL_DELETION)
    except ActionTokenError as exc:
        raise token_error(exc) from exc
    user = await lock_user(db, owner_id)
    if user is None:
        raise _action_required()
    deletion = (
        await db.execute(
            select(AccountDeletion)
            .where(AccountDeletion.id == deletion_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if deletion is None or deletion.user_id != user.id:
        raise _action_required()
    fingerprint = _cancel_fingerprint(deletion.id, request_id)
    if deletion.state == "cancelled":
        if deletion.cancel_request_id == request_id and deletion.cancel_fingerprint == fingerprint:
            return deletion
        raise CredentialError(409, "operation_id_conflict")
    if deletion.state != "grace" or now >= deletion.cancel_until:
        raise CredentialError(409, "deletion_irreversible")
    try:
        row = await consume_action_token(db, user, token, CANCEL_DELETION, now=now)
    except ActionTokenError as exc:
        raise token_error(exc) from exc
    if row.target_deletion_id != deletion.id:
        raise _action_required()
    deletion.state = "cancelled"
    deletion.stage = "cancelled"
    deletion.cancelled_at = now
    deletion.cancel_request_id = request_id
    deletion.cancel_fingerprint = fingerprint
    deletion.next_attempt_at = None
    user.account_status = "active"
    user.lifecycle_revision = user.lifecycle_revision + 1
    await db.flush()
    await _invalidate_user_proofs(db, user.id, now)
    if user.email_verified_at is not None:
        locale = normalize_locale(await profile_locale(db, user.id))
        await queue_account_mail(
            db,
            user,
            CANCELLED_KIND,
            render_deletion_cancelled(locale),
            expires_at=now + NOTICE_TTL,
            now=now,
        )
    return deletion


async def deletion_status(
    db: AsyncSession,
    *,
    request_id: UUID | None,
    status_secret: str | None,
    action_token: str | None,
    now: datetime | None = None,
) -> AccountDeletion:
    """Read-only. A receipt or a cancel proof is the only way to learn anything."""
    now = now or now_utc()
    if request_id is not None and status_secret is not None and action_token is None:
        deletion = await db.get(AccountDeletion, request_id)
        # A wiped secret never matches, so old receipts stop answering after the retention window.
        if (
            deletion is None
            or not deletion.status_secret_hash
            or not hmac.compare_digest(deletion.status_secret_hash, secret_hash(status_secret))
        ):
            raise CredentialError(404, "deletion_not_found")
        return deletion
    if action_token is not None and request_id is None and status_secret is None:
        try:
            owner_id = await find_token_owner(db, action_token, CANCEL_DELETION)
            user = await db.get(User, owner_id)
            if user is None:
                raise _action_required()
            row = await peek_action_token(db, user, action_token, CANCEL_DELETION, now=now)
        except ActionTokenError as exc:
            raise token_error(exc) from exc
        deletion = (
            await db.get(AccountDeletion, row.target_deletion_id)
            if row.target_deletion_id
            else None
        )
        if deletion is None:
            raise CredentialError(404, "deletion_not_found")
        return deletion
    raise CredentialError(422, "deletion_status_input_invalid")
