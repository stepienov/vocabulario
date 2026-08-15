import re
import unicodedata
from uuid import UUID

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http_errors import api_error
from app.core.security import verify_token_type
from app.db.session import get_db
from app.models import User

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "not_authenticated", "Not authenticated")
    try:
        from app.core.security import decode_token

        payload = decode_token(credentials.credentials)
        user_id = verify_token_type(payload, "access")
    except (JWTError, ValueError) as exc:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "invalid_token", "Invalid token") from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "user_not_found", "User not found")
    return user


def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return unicodedata.normalize("NFC", text)


def lang_pair_key(native: str, learning: str) -> str:
    return f"{native}>{learning}"
