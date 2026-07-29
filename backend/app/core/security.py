from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()
    return create_token(
        str(user_id),
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: UUID) -> str:
    settings = get_settings()
    return create_token(
        str(user_id),
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def verify_token_type(payload: dict[str, Any], expected: str) -> UUID:
    if payload.get("type") != expected:
        raise JWTError("Invalid token type")
    sub = payload.get("sub")
    if not sub:
        raise JWTError("Missing subject")
    return UUID(sub)
