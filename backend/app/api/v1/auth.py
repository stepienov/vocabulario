import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.http_errors import api_error
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models import LanguageProfile, User, UserSettings
from app.schemas import (
    GoogleAuthRequest,
    LanguageProfileCreate,
    LanguageProfileResponse,
    LanguageProfileUpdate,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    UserSettingsResponse,
    UserSettingsUpdate,
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
from app.services.llm import verify_google_id_token

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
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise api_error(status.HTTP_409_CONFLICT, "email_taken", "Email already registered")

    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    db.add(user)
    await db.flush()
    await _ensure_settings(db, user.id)
    issued = await create_session(db, user.id)
    await db.commit()
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
    if not verify_password(body.password, verified_hash):
        raise api_error(status.HTTP_401_UNAUTHORIZED, "wrong_password", "Wrong password")
    # The password may have changed while it was being verified; re-check under the lock.
    locked = await lock_user(db, user.id)
    if locked is None or locked.password_hash != verified_hash:
        await db.rollback()
        raise api_error(status.HTTP_401_UNAUTHORIZED, "wrong_password", "Wrong password")
    issued = await create_session(db, user.id)
    await db.commit()
    return _token_response(issued, response)


@router.post("/google", response_model=TokenResponse)
async def google_auth(body: GoogleAuthRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        token_data = await verify_google_id_token(body.id_token)
    except Exception as exc:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "invalid_google_token", "Invalid Google token") from exc

    google_id = token_data["sub"]
    email = token_data["email"].lower()

    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()
    if user is None:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            user.google_id = google_id
        else:
            user = User(email=email, google_id=google_id)
            db.add(user)
            await db.flush()
            await _ensure_settings(db, user.id)

    await db.flush()
    await lock_user(db, user.id)
    issued = await create_session(db, user.id)
    await db.commit()
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


me_router = APIRouter(prefix="/me", tags=["me"])


@me_router.get("", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return user


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
async def list_profiles(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LanguageProfile).where(LanguageProfile.user_id == user.id))
    return list(result.scalars().all())


@profiles_router.post("", response_model=LanguageProfileResponse)
async def create_profile(
    body: LanguageProfileCreate,
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
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
