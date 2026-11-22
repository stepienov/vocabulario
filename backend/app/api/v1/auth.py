import hashlib
import json
import logging
import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings as get_app_settings
from app.core.deps import get_current_user, get_verified_user
from app.core.http_errors import api_error
from app.core.passwords import (
    dummy_verify,
    hash_new_password,
    is_legacy_bcrypt,
    password_error,
    verify_current_password,
)
from app.core.security import REFRESH, TokenError, now_utc, read_token
from app.db.session import get_db
from app.models import LanguageProfile, User, UserSettings
from app.schemas import (
    AddPasswordRequest,
    EmailVerificationConfirm,
    EmailVerificationStatusResponse,
    GoogleAuthRequest,
    GoogleChallengeResponse,
    GoogleLinkChallengeRequest,
    GoogleLinkRequest,
    LanguageProfileCreate,
    LanguageProfileResponse,
    LanguageProfileUpdate,
    LegalAcceptanceIn,
    LegalStatus,
    LoginRequest,
    LogoutRequest,
    MailAcceptedResponse,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetResponse,
    RecentAuthGoogleChallengeRequest,
    RecentAuthGoogleRequest,
    RecentAuthPasswordRequest,
    RecentAuthResponse,
    RefreshRequest,
    RegisterRequest,
    StatusResponse,
    TokenResponse,
    UserResponse,
    UserSettingsResponse,
    UserSettingsUpdate,
)
from app.services.account_recovery import (
    RETRY_AFTER_SECONDS,
    CredentialError,
    MailRateLimited,
    add_password,
    change_password,
    confirm_email_verification,
    confirm_password_reset,
    ensure_mail_available,
    queue_verification_mail,
    request_email_verification,
    request_password_reset,
    verification_status,
)
from app.services.action_tokens import ActionTokenError
from app.services.account_lifecycle import lifecycle_override
from app.services.recent_auth import issue_password_proof
from app.services.auth_limits import (
    MIN,
    LimiterUnavailable,
    RateLimited,
    Rule,
    client_ip,
    enforce,
    reserve,
)
from app.services.auth_sessions import (
    IssuedSession,
    RetryRecordError,
    SessionAuthError,
    create_session,
    lock_user,
    logout_session,
    refresh_session,
)
from app.services.google_auth import google_login, link_google, recent_auth_google
from app.services.google_challenges import (
    issue_link_challenge,
    issue_login_challenge,
    issue_recent_auth_challenge,
)
from app.services.mail_events import WebhookRejected, handle_webhook
from app.services.mail_outbox import wake_mail_worker
from app.services.legal_docs import (
    CODE_ACCEPTANCE_MISSING,
    Acceptance,
    apply_acceptance,
    check_acceptance,
    legal_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _acceptance(body) -> Acceptance | None:
    if body is None:
        return None
    return Acceptance(body.terms_version, body.locale, body.adult_confirmed)


def _public(ip: str) -> Rule:
    """Every public POST of this router counts here, except the provider webhook."""
    return Rule("auth_public_ip", ip, 120, 15 * MIN)


def _invalid_credentials() -> HTTPException:
    return api_error(
        status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "Invalid e-mail or password"
    )


def _token_response(issued: IssuedSession, response: Response) -> TokenResponse:
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        user_id=issued.user_id,
        session_id=issued.session_id,
        expires_in=issued.expires_in(),
    )


async def _session_error(db: AsyncSession, exc: SessionAuthError):
    if exc.commit:
        await db.commit()
    else:
        await db.rollback()
    return api_error(exc.status_code, exc.code)


async def _ensure_settings(db: AsyncSession, user_id) -> UserSettings:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        await db.flush()
    return settings


@router.post("/register", response_model=TokenResponse)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    ip = client_ip(request)
    await enforce(_public(ip), Rule("auth_register_ip", ip, 30, 60 * MIN))
    code = password_error(body.password, new=True)
    if code is not None:
        raise api_error(422, code.value)
    acceptance = _acceptance(body.legal_acceptance)
    if acceptance is not None:
        check_acceptance(acceptance)
    elif get_app_settings().legal_acceptance_enforced:
        raise api_error(422, CODE_ACCEPTANCE_MISSING)
    try:
        await ensure_mail_available()
    except CredentialError as exc:
        raise api_error(exc.status_code, exc.code) from exc
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise api_error(status.HTTP_409_CONFLICT, "email_taken", "Email already registered")

    user = User(email=body.email.lower(), password_hash=await hash_new_password(body.password))
    now = now_utc()
    if acceptance is not None:
        apply_acceptance(user, acceptance, now)
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        # Two registrations for one address raced; the loser gets the normal conflict.
        if "email" not in str(exc.orig):
            raise
        await db.rollback()
        raise api_error(
            status.HTTP_409_CONFLICT, "email_taken", "Email already registered"
        ) from exc
    await _ensure_settings(db, user.id)
    issued = await create_session(db, user.id)
    # Same transaction as the account: success means the first mail is durably queued.
    await queue_verification_mail(db, user, body.locale, now=now)
    await db.commit()
    wake_mail_worker()
    return _token_response(issued, response)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    ip = client_ip(request)
    email = body.email.lower()
    await enforce(
        _public(ip),
        Rule("auth_login_ip", ip, 20, 15 * MIN),
        Rule("auth_login_pair", f"{ip}|{email}", 5, 5 * MIN),
    )
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    verified_hash = user.password_hash if user else None
    if not verified_hash:
        # Unknown and Google-only addresses cost the same work and answer the same way.
        await dummy_verify(body.password)
        raise _invalid_credentials()
    if not await verify_current_password(body.password, verified_hash):
        raise _invalid_credentials()
    # The password may have changed while it was being verified; re-check under the lock.
    locked = await lock_user(db, user.id)
    if locked is None or locked.password_hash != verified_hash:
        await db.rollback()
        raise _invalid_credentials()
    if locked.account_status != "active":
        await db.rollback()
        raise api_error(status.HTTP_403_FORBIDDEN, "account_deletion_pending")
    if locked.restore_recovery_required:
        # After a restore the stored credentials may predate the user's last change; only a
        # fresh reset or Google proof reopens the account. Reached with a matching password only.
        await db.rollback()
        raise api_error(status.HTTP_403_FORBIDDEN, "restore_recovery_required")
    issued = await create_session(db, user.id)
    await db.commit()
    return _token_response(issued, response)


def _google_error(exc: CredentialError) -> HTTPException:
    return api_error(exc.status_code, exc.code)


@router.post("/google/challenge", response_model=GoogleChallengeResponse)
async def google_challenge(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> GoogleChallengeResponse:
    """Public: a nonce for one Google sign-in; nothing about any account is revealed."""
    ip = client_ip(request)
    await enforce(_public(ip), Rule("auth_google_challenge_ip", ip, 30, 15 * MIN))
    issued = await issue_login_challenge(db)
    result = GoogleChallengeResponse(
        challenge_id=issued.id, nonce=issued.nonce, expires_at=issued.expires_at
    )
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/google", response_model=TokenResponse)
async def google_auth(
    body: GoogleAuthRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    ip = client_ip(request)
    await enforce(_public(ip), Rule("auth_login_ip", ip, 20, 15 * MIN))
    try:
        login = await google_login(
            db, body.challenge_id, body.id_token, body.locale, acceptance=_acceptance(body.legal_acceptance)
        )
    except CredentialError as exc:
        await db.rollback()
        raise _google_error(exc) from exc
    await db.commit()
    if login.mail_queued:
        wake_mail_worker()
    return _token_response(login.issued, response)


@router.post("/google/link/challenge", response_model=GoogleChallengeResponse)
async def google_link_challenge(
    body: GoogleLinkChallengeRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoogleChallengeResponse:
    ctx = request.state.auth_context
    await enforce(Rule("auth_google_link_session", str(ctx.session_id), 10, 15 * MIN))
    try:
        issued = await issue_link_challenge(db, user, ctx, body.recent_auth_token)
    except CredentialError as exc:
        raise await _rollback_error(db, exc) from exc
    result = GoogleChallengeResponse(
        challenge_id=issued.id, nonce=issued.nonce, expires_at=issued.expires_at
    )
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/google/link", response_model=TokenResponse)
async def google_link(
    body: GoogleLinkRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ctx = request.state.auth_context
    await enforce(Rule("auth_google_link_user", str(user.id), 10, 60 * MIN))
    try:
        issued = await link_google(
            db, user, ctx, body.challenge_id, body.id_token, body.recent_auth_token
        )
    except CredentialError as exc:
        raise await _rollback_error(db, exc) from exc
    except SessionAuthError as exc:
        raise await _session_error(db, exc) from exc
    await db.commit()
    wake_mail_worker()
    return _token_response(issued, response)


@router.post("/recent-auth/google/challenge", response_model=GoogleChallengeResponse)
async def recent_auth_google_challenge(
    body: RecentAuthGoogleChallengeRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoogleChallengeResponse:
    ctx = request.state.auth_context
    await enforce(
        Rule("auth_recent_session", str(ctx.session_id), 5, 5 * MIN),
        Rule("auth_recent_ip", client_ip(request), 20, 15 * MIN),
    )
    try:
        issued = await issue_recent_auth_challenge(db, user, ctx, body.action)
    except CredentialError as exc:
        raise await _rollback_error(db, exc) from exc
    result = GoogleChallengeResponse(
        challenge_id=issued.id, nonce=issued.nonce, expires_at=issued.expires_at
    )
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/recent-auth/google", response_model=RecentAuthResponse)
async def recent_auth_google_proof(
    body: RecentAuthGoogleRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecentAuthResponse:
    ctx = request.state.auth_context
    await enforce(
        Rule("auth_recent_session", str(ctx.session_id), 5, 5 * MIN),
        Rule("auth_recent_ip", client_ip(request), 20, 15 * MIN),
    )
    try:
        token, proof = await recent_auth_google(
            db, user, ctx, body.challenge_id, body.id_token, body.action
        )
    except CredentialError as exc:
        raise await _rollback_error(db, exc) from exc
    except SessionAuthError as exc:
        raise await _session_error(db, exc) from exc
    result = RecentAuthResponse(
        recent_auth_token=token, action=proof.action, expires_at=proof.expires_at
    )
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


async def _lifecycle_refresh_error(db: AsyncSession, refresh_token: str) -> None:
    """A signed refresh token of a pending or erased account gets the lifecycle answer."""
    try:
        claims = read_token(refresh_token, REFRESH, allow_expired_refresh=True)
    except TokenError:
        return
    await db.rollback()
    override = await lifecycle_override(db, claims.user_id, claims.session_id)
    if override is not None:
        await db.rollback()
        raise api_error(*override)
    await db.rollback()


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    rules = [_public(client_ip(request))]
    try:
        claims = read_token(body.refresh_token, REFRESH, allow_expired_refresh=True)
        rules.append(Rule("auth_refresh_session", str(claims.session_id), 60, 15 * MIN))
    except TokenError:
        pass  # the session layer answers the bad token; only the IP rule applies
    await enforce(*rules)
    try:
        issued = await refresh_session(db, body.refresh_token, body.request_id)
    except SessionAuthError as exc:
        if exc.code == "session_revoked" and not exc.commit:
            await _lifecycle_refresh_error(db, body.refresh_token)
        raise await _session_error(db, exc) from exc
    except RetryRecordError as exc:
        await db.rollback()
        logger.error("auth refresh retry record unusable: %s", exc)
        raise api_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "refresh_unavailable", "Refresh failed"
        ) from exc
    await db.commit()
    return _token_response(issued, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    await enforce(_public(client_ip(request)))
    try:
        await logout_session(db, body.refresh_token)
    except SessionAuthError as exc:
        raise await _session_error(db, exc) from exc
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _rollback_error(db: AsyncSession, exc: ActionTokenError | CredentialError):
    await db.rollback()
    return api_error(exc.status_code, exc.code)


@router.post(
    "/password-reset/request",
    response_model=MailAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def password_reset_request(
    body: PasswordResetRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> MailAcceptedResponse:
    """Same answer for every address; never reveals whether an account exists."""
    ip = client_ip(request)
    await enforce(_public(ip), Rule("auth_reset_ip", ip, 20, 15 * MIN))
    try:
        await ensure_mail_available()
    except CredentialError as exc:
        raise api_error(exc.status_code, exc.code) from exc
    address = str(body.email).lower()
    try:
        # Counted for unknown and Google-only addresses too; a full bucket still answers 202.
        await reserve(
            Rule("mail_reset_addr_cooldown", address, 1, MIN),
            Rule("mail_reset_addr_hour", address, 3, 60 * MIN),
            now=now_utc(),
        )
    except RateLimited:
        return MailAcceptedResponse(retry_after_seconds=RETRY_AFTER_SECONDS)
    except LimiterUnavailable as exc:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_temporarily_unavailable") from exc
    queued = await request_password_reset(db, address, body.locale)
    await db.commit()
    if queued:
        wake_mail_worker()
    return MailAcceptedResponse(retry_after_seconds=RETRY_AFTER_SECONDS)


@router.post("/password-reset/confirm", response_model=PasswordResetResponse)
async def password_reset_confirm(
    body: PasswordResetConfirm, request: Request, db: AsyncSession = Depends(get_db)
) -> PasswordResetResponse:
    ip = client_ip(request)
    await enforce(_public(ip), Rule("auth_confirm_ip", ip, 30, 15 * MIN))
    try:
        await confirm_password_reset(db, body.token, body.new_password)
    except (ActionTokenError, CredentialError) as exc:
        raise await _rollback_error(db, exc) from exc
    await db.commit()
    wake_mail_worker()
    return PasswordResetResponse()


@router.post("/password/change", response_model=TokenResponse)
async def password_change(
    body: PasswordChangeRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await enforce(Rule("auth_password_change_user", str(user.id), 5, 60 * MIN))
    session_id = request.state.auth_context.session_id
    try:
        issued = await change_password(
            db, user, session_id, body.current_password, body.new_password
        )
    except CredentialError as exc:
        raise await _rollback_error(db, exc) from exc
    except SessionAuthError as exc:
        raise await _session_error(db, exc) from exc
    await db.commit()
    wake_mail_worker()
    return _token_response(issued, response)


@router.post(
    "/email-verification/request",
    response_model=MailAcceptedResponse | StatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def email_verification_request(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await ensure_mail_available()
        queued = await request_email_verification(db, user.id)
    except CredentialError as exc:
        raise await _rollback_error(db, exc) from exc
    except SessionAuthError as exc:
        raise await _session_error(db, exc) from exc
    except MailRateLimited as exc:
        await db.rollback()
        wait_s = max(1, math.ceil((exc.retry_at - now_utc()).total_seconds()))
        raise api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "mail_rate_limited",
            headers={"Retry-After": str(wait_s)},
        ) from exc
    await db.commit()
    if not queued:
        response.status_code = status.HTTP_200_OK
        return StatusResponse(status="already_verified")
    wake_mail_worker()
    return MailAcceptedResponse(retry_after_seconds=RETRY_AFTER_SECONDS)


@router.get("/email-verification/status", response_model=EmailVerificationStatusResponse)
async def email_verification_status(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> EmailVerificationStatusResponse:
    state = await verification_status(db, user)
    return EmailVerificationStatusResponse(
        email_verified=state.email_verified,
        delivery_status=state.delivery_status,
        delivery_delayed=state.delivery_delayed,
        resend_available_at=state.resend_available_at,
    )


@router.post("/email-verification/confirm", response_model=StatusResponse)
async def email_verification_confirm(
    body: EmailVerificationConfirm, request: Request, db: AsyncSession = Depends(get_db)
) -> StatusResponse:
    ip = client_ip(request)
    await enforce(_public(ip), Rule("auth_confirm_ip", ip, 30, 15 * MIN))
    try:
        await confirm_email_verification(db, body.token)
    except ActionTokenError as exc:
        raise await _rollback_error(db, exc) from exc
    await db.commit()
    return StatusResponse(status="email_verified")


@router.post("/recent-auth/password", response_model=RecentAuthResponse)
async def recent_auth_password(
    body: RecentAuthPasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecentAuthResponse:
    ctx = request.state.auth_context
    await enforce(
        Rule("auth_recent_session", str(ctx.session_id), 5, 5 * MIN),
        Rule("auth_recent_ip", client_ip(request), 20, 15 * MIN),
    )
    try:
        token, proof = await issue_password_proof(db, user, ctx, body.action, body.password)
    except CredentialError as exc:
        raise await _rollback_error(db, exc) from exc
    result = RecentAuthResponse(
        recent_auth_token=token, action=proof.action, expires_at=proof.expires_at
    )
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/password/add", response_model=TokenResponse)
async def password_add(
    body: AddPasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await enforce(Rule("auth_password_add_user", str(user.id), 5, 60 * MIN))
    try:
        issued = await add_password(
            db, user, request.state.auth_context, body.new_password, body.recent_auth_token
        )
    except CredentialError as exc:
        raise await _rollback_error(db, exc) from exc
    except SessionAuthError as exc:
        raise await _session_error(db, exc) from exc
    await db.commit()
    wake_mail_worker()
    return _token_response(issued, response)


@router.post("/mail-events", status_code=status.HTTP_204_NO_CONTENT)
async def mail_events(request: Request) -> Response:
    """Resend delivery events (Svix-signed). Never confirms an address or a password."""
    body = await request.body()
    try:
        await handle_webhook(body, dict(request.headers))
    except WebhookRejected as exc:
        raise api_error(exc.status_code, exc.code) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


me_router = APIRouter(prefix="/me", tags=["me"])


@me_router.get("", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    methods = [
        name
        for name, value in (("password", user.password_hash), ("google", user.google_id))
        if value
    ]
    verified = user.email_verified_at is not None
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        email_verified=verified,
        email_verification_required=get_app_settings().email_verification_gate and not verified,
        login_methods=methods,
        password_upgrade_required=bool(user.password_hash)
        and is_legacy_bcrypt(user.password_hash),
        email_revision=user.email_revision,
        account_status=user.account_status,
        lifecycle_revision=user.lifecycle_revision,
        google_email=user.google_email if user.google_id else None,
        google_email_observed_at=user.google_email_observed_at if user.google_id else None,
        legal_status=legal_status(user),
    )


@me_router.post("/legal-acceptance", response_model=LegalStatus)
async def accept_legal(
    body: LegalAcceptanceIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LegalStatus:
    """Idempotent: a repeat of the accepted version keeps the original time."""
    acceptance = Acceptance(body.terms_version, body.locale, body.adult_confirmed)
    check_acceptance(acceptance)
    locked = await lock_user(db, user.id)
    if locked is None or locked.account_status != "active":
        await db.rollback()
        raise api_error(status.HTTP_403_FORBIDDEN, "account_deletion_pending")
    changed = apply_acceptance(locked, acceptance, now_utc())
    result = LegalStatus(**legal_status(locked))
    if changed:
        await db.commit()
    else:
        await db.rollback()
    return result


@me_router.get("/settings", response_model=UserSettingsResponse)
async def get_settings(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    settings = await _ensure_settings(db, user.id)
    await db.commit()
    return settings


@me_router.put("/settings", response_model=UserSettingsResponse)
async def update_settings(
    body: UserSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await _ensure_settings(db, user.id)
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(settings, field, value)
    await db.commit()
    await db.refresh(settings)
    return settings


profiles_router = APIRouter(prefix="/profiles", tags=["profiles"])


def _profile_mutation_fingerprint(fields: dict, expected_revision: int | None) -> str:
    canonical = json.dumps(
        {"fields": fields, "expected_revision": expected_revision}, sort_keys=True, ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


@profiles_router.get("", response_model=list[LanguageProfileResponse])
async def list_profiles(user: User = Depends(get_verified_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LanguageProfile).where(LanguageProfile.user_id == user.id))
    return list(result.scalars().all())


@profiles_router.post("", response_model=LanguageProfileResponse)
async def create_profile(
    body: LanguageProfileCreate,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LanguageProfile).where(
            LanguageProfile.user_id == user.id,
            LanguageProfile.is_active.is_(True),
        )
    )
    for p in result.scalars():
        p.is_active = False

    profile = LanguageProfile(
        user_id=user.id,
        app_lang=body.app_lang,
        learning_lang=body.learning_lang,
        cefr_level=body.cefr_level,
        selected_tenses=body.selected_tenses,
        tense_label_lang=body.tense_label_lang,
        is_active=True,
    )
    db.add(profile)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise api_error(status.HTTP_409_CONFLICT, "profile_pair_exists", "A profile with this language pair already exists")
    await db.refresh(profile)
    return profile


@profiles_router.put("/{profile_id}", response_model=LanguageProfileResponse)
async def update_profile(
    profile_id: str,
    body: LanguageProfileUpdate,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    from uuid import UUID

    pid = UUID(profile_id)
    result = await db.execute(
        select(LanguageProfile)
        .where(LanguageProfile.id == pid, LanguageProfile.user_id == user.id)
        .with_for_update()
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise api_error(404, "profile_not_found", "Profile not found")

    fields = {
        key: value
        for key, value in body.model_dump(
            exclude_unset=True, exclude={"expected_revision", "client_op_id"}
        ).items()
        if value is not None
    }
    fingerprint = _profile_mutation_fingerprint(fields, body.expected_revision)
    op_id = body.client_op_id
    if op_id is not None and profile.last_mutation_id == op_id:
        if profile.last_mutation_fingerprint != fingerprint:
            raise api_error(
                status.HTTP_409_CONFLICT,
                "operation_id_conflict",
                "This operation id was already used with different content",
            )
        return profile
    if body.expected_revision is None:
        if get_app_settings().profile_update_requires_revision:
            raise api_error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "expected_revision_required",
                "expected_revision is required",
            )
    elif body.expected_revision != profile.revision:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "profile_conflict",
            "The profile was changed on another device",
        )

    if fields:
        for field, value in fields.items():
            setattr(profile, field, value)
        profile.revision = profile.revision + 1
        profile.last_mutation_id = op_id
        profile.last_mutation_fingerprint = fingerprint if op_id is not None else None
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise api_error(status.HTTP_409_CONFLICT, "profile_pair_exists", "A profile with this language pair already exists")
    await db.refresh(profile)
    return profile


@profiles_router.put("/{profile_id}/activate", response_model=LanguageProfileResponse)
async def activate_profile(
    profile_id: str,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    from uuid import UUID
    from datetime import UTC, datetime

    pid = UUID(profile_id)
    result = await db.execute(
        select(LanguageProfile).where(
            LanguageProfile.user_id == user.id,
        )
    )
    profiles = list(result.scalars().all())
    active = None
    for p in profiles:
        p.is_active = p.id == pid
        if p.is_active:
            p.last_used_at = datetime.now(UTC)
            active = p
    if active is None:
        raise api_error(404, "profile_not_found", "Profile not found")
    await db.commit()
    await db.refresh(active)
    return active
