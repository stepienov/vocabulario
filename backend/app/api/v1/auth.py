from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.http_errors import api_error
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_token_type,
)
from app.db.session import get_db
from app.models import LanguageProfile, User, UserSettings
from app.schemas import (
    GoogleAuthRequest,
    LanguageProfileCreate,
    LanguageProfileResponse,
    LanguageProfileUpdate,
    LoginRequest,
    RegisterRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
    UserSettingsResponse,
    UserSettingsUpdate,
)
from app.services.llm import verify_google_id_token

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_tokens(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


async def _ensure_settings(db: AsyncSession, user_id) -> UserSettings:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        await db.flush()
    return settings


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise api_error(status.HTTP_409_CONFLICT, "email_taken", "Email already registered")

    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    db.add(user)
    await db.flush()
    await _ensure_settings(db, user.id)
    await db.commit()
    await db.refresh(user)
    return await _issue_tokens(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
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
    if not verify_password(body.password, user.password_hash):
        raise api_error(status.HTTP_401_UNAUTHORIZED, "wrong_password", "Wrong password")
    return await _issue_tokens(user)


@router.post("/google", response_model=TokenResponse)
async def google_auth(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
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

    await db.commit()
    await db.refresh(user)
    return await _issue_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        user_id = verify_token_type(payload, "refresh")
    except Exception as exc:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "invalid_refresh_token", "Invalid refresh token") from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "user_not_found", "User not found")
    return await _issue_tokens(user)


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
    await db.commit()
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
    await db.commit()
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
