import logging
import math

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings as get_app_settings
from app.core.deps import get_current_user, get_verified_user
from app.core.http_errors import api_error
from app.core.passwords import verify_current_password
from app.core.security import hash_password, now_utc
from app.db.session import get_db
from app.models import LanguageProfile, User, UserSettings
from app.schemas import (
    EmailVerificationConfirm,
    EmailVerificationStatusResponse,
    GoogleAuthRequest,
    LanguageProfileCreate,
    LanguageProfileResponse,
    LanguageProfileUpdate,
    LoginRequest,
    LogoutRequest,
    MailAcceptedResponse,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetResponse,
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
from app.services.auth_sessions import (
    IssuedSession,
    RetryRecordError,
    SessionAuthError,
    create_session,
    lock_user,
    logout_session,
    refresh_session,
)
from app.services.llm import verify_google_id_token
from app.services.mail_outbox import wake_mail_worker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


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
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        ensure_mail_available()
    except CredentialError as exc:
        raise api_error(exc.status_code, exc.code) from exc
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise api_error(status.HTTP_409_CONFLICT, "email_taken", "Email already registered")

    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    db.add(user)
    await db.flush()
    await _ensure_settings(db, user.id)
    issued = await create_session(db, user.id)
    # Same transaction as the account: success means the first mail is durably queued.
    await queue_verification_mail(db, user, body.locale, now=now_utc())
    await db.commit()
    wake_mail_worker()
    return _token_response(issued, response)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if user is None:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "email_not_found", "No account with this email")
    if not user.password_hash:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "google_login_required",
            "This account uses Google sign-in",
        )
    verified_hash = user.password_hash
    if not await verify_current_password(body.password, verified_hash):
        raise api_error(status.HTTP_401_UNAUTHORIZED, "wrong_password", "Wrong password")
    # The password may have changed while it was being verified; re-check under the lock.
    locked = await lock_user(db, user.id)
    if locked is None or locked.password_hash != verified_hash:
        await db.rollback()
        raise api_error(status.HTTP_401_UNAUTHORIZED, "wrong_password", "Wrong password")
    issued = await create_session(db, user.id)
    await db.commit()
    return _token_response(issued, response)


def _google_proves_address(token_data: dict, email: str) -> bool:
    """F-005 trust rule: only Gmail or a Workspace (`hd`) address Google itself verified.

    tokeninfo sends `email_verified` as the string "true"; google-auth sends a bool.
    """
    if token_data.get("email_verified") not in (True, "true"):
        return False
    return email.rpartition("@")[2] == "gmail.com" or bool(token_data.get("hd"))


@router.post("/google", response_model=TokenResponse)
async def google_auth(body: GoogleAuthRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        token_data = await verify_google_id_token(body.id_token)
    except Exception as exc:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "invalid_google_token", "Invalid Google token") from exc

    google_id = token_data["sub"]
    email = token_data["email"].lower()
    proven = _google_proves_address(token_data, email)
    queue_mail = False

    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()
    trusted = user is not None
    if user is None:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            # Linking by e-mail is no proof: the address may have been pre-registered by someone else.
            user.google_id = google_id
        else:
            trusted = True
            queue_mail = not proven
            if queue_mail:
                try:
                    ensure_mail_available()
                except CredentialError as exc:
                    raise api_error(exc.status_code, exc.code) from exc
            user = User(email=email, google_id=google_id)
            db.add(user)
            await db.flush()
            await _ensure_settings(db, user.id)

    await db.flush()
    await lock_user(db, user.id)
    now = now_utc()
    if trusted and proven and user.email == email and user.email_verified_at is None:
        user.email_verified_at = now
    issued = await create_session(db, user.id)
    if queue_mail:
        await queue_verification_mail(db, user, body.locale, now=now)
    await db.commit()
    if queue_mail:
        wake_mail_worker()
    return _token_response(issued, response)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        issued = await refresh_session(db, body.refresh_token, body.request_id)
    except SessionAuthError as exc:
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
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)) -> Response:
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
    body: PasswordResetRequest, db: AsyncSession = Depends(get_db)
) -> MailAcceptedResponse:
    """Same answer for every address; never reveals whether an account exists."""
    try:
        ensure_mail_available()
    except CredentialError as exc:
        raise api_error(exc.status_code, exc.code) from exc
    queued = await request_password_reset(db, str(body.email), body.locale)
    await db.commit()
    if queued:
        wake_mail_worker()
    return MailAcceptedResponse(retry_after_seconds=RETRY_AFTER_SECONDS)


@router.post("/password-reset/confirm", response_model=PasswordResetResponse)
async def password_reset_confirm(
    body: PasswordResetConfirm, db: AsyncSession = Depends(get_db)
) -> PasswordResetResponse:
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
        ensure_mail_available()
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
    body: EmailVerificationConfirm, db: AsyncSession = Depends(get_db)
) -> StatusResponse:
    try:
        await confirm_email_verification(db, body.token)
    except ActionTokenError as exc:
        raise await _rollback_error(db, exc) from exc
    await db.commit()
    return StatusResponse(status="email_verified")


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
    )


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
        select(LanguageProfile).where(
            LanguageProfile.id == pid,
            LanguageProfile.user_id == user.id,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise api_error(404, "profile_not_found", "Profile not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
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
