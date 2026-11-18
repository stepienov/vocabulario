import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_ISSUER = "vocabulario-api"
JWT_AUDIENCE = "vocabulario-android"
TOKEN_PROTOCOL_VERSION = 2
ACCESS = "access"
REFRESH = "refresh"


def now_utc() -> datetime:
    """Single clock for token and session logic; tests may monkeypatch it."""
    return datetime.fromtimestamp(time.time(), UTC)


class TokenError(Exception):
    """`reason` is `invalid`, `expired` or `legacy` (valid pre-v2 token, never authorizes)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    session_id: UUID
    session_version: int
    token_id: UUID
    token_type: str
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access: TokenClaims
    refresh: TokenClaims


def _ttl(token_type: str) -> timedelta:
    settings = get_settings()
    if token_type == ACCESS:
        return timedelta(minutes=settings.access_token_expire_minutes)
    return timedelta(days=settings.refresh_token_expire_days)


def _encode(claims: TokenClaims) -> str:
    settings = get_settings()
    payload: dict[str, Any] = {
        "v": TOKEN_PROTOCOL_VERSION,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "sub": str(claims.user_id),
        "sid": str(claims.session_id),
        "sv": claims.session_version,
        "jti": str(claims.token_id),
        "type": claims.token_type,
        "iat": int(claims.issued_at.timestamp()),
        "exp": int(claims.expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def issue_token_pair(
    user_id: UUID, session_id: UUID, session_version: int, now: datetime
) -> TokenPair:
    issued = datetime.fromtimestamp(int(now.timestamp()), UTC)
    claims = {
        token_type: TokenClaims(
            user_id=user_id,
            session_id=session_id,
            session_version=session_version,
            token_id=uuid4(),
            token_type=token_type,
            issued_at=issued,
            expires_at=issued + _ttl(token_type),
        )
        for token_type in (ACCESS, REFRESH)
    }
    return TokenPair(
        access_token=_encode(claims[ACCESS]),
        refresh_token=_encode(claims[REFRESH]),
        access=claims[ACCESS],
        refresh=claims[REFRESH],
    )


def _uuid(value: Any) -> UUID:
    if not isinstance(value, str):
        raise TokenError("invalid")
    try:
        return UUID(value)
    except ValueError as exc:
        raise TokenError("invalid") from exc


def _int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TokenError("invalid")
    return value


def read_token(token: str, expected_type: str, *, now: datetime | None = None) -> TokenClaims:
    """Verify signature and the full v2 contract; never trusts the token's own `alg`."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False, "verify_iss": False, "verify_exp": False},
        )
    except (JWTError, ValueError, TypeError) as exc:
        raise TokenError("invalid") from exc
    if not isinstance(payload, dict):
        raise TokenError("invalid")
    current = (now or now_utc()).timestamp()
    if "v" not in payload:
        if payload.get("type") != expected_type:
            raise TokenError("invalid")
        _uuid(payload.get("sub"))
        if _int(payload.get("exp")) <= current:
            raise TokenError("invalid")
        raise TokenError("legacy")
    if _int(payload["v"]) != TOKEN_PROTOCOL_VERSION:
        raise TokenError("invalid")
    if payload.get("iss") != JWT_ISSUER or payload.get("aud") != JWT_AUDIENCE:
        raise TokenError("invalid")
    if payload.get("type") != expected_type:
        raise TokenError("invalid")
    version = _int(payload.get("sv"))
    issued_at = _int(payload.get("iat"))
    expires_at = _int(payload.get("exp"))
    if version < 1 or expires_at <= issued_at:
        raise TokenError("invalid")
    claims = TokenClaims(
        user_id=_uuid(payload.get("sub")),
        session_id=_uuid(payload.get("sid")),
        session_version=version,
        token_id=_uuid(payload.get("jti")),
        token_type=expected_type,
        issued_at=datetime.fromtimestamp(issued_at, UTC),
        expires_at=datetime.fromtimestamp(expires_at, UTC),
    )
    if expires_at <= current:
        raise TokenError("expired")
    return claims


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def token_subject(token: str) -> UUID | None:
    """Signed, unexpired `sub` for log attribution only; never an authorization decision."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False, "verify_iss": False},
        )
        return UUID(str(payload["sub"]))
    except (JWTError, ValueError, TypeError, KeyError):
        return None
