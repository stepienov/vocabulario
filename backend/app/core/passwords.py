"""Password policy and Argon2id hashing (E-001/F-004/T-001).

Characters are Unicode scalar values (Python code points without lone surrogates).
Passwords are hashed exactly as accepted: no trimming, normalization or truncation.
`verify_password` never accepts legacy bcrypt; only the transitional
`verify_current_password` still does until the bcrypt cutoff.
"""

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from secrets import token_urlsafe

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

logger = logging.getLogger(__name__)

NEW_PASSWORD_MIN_CHARS = 15
PASSWORD_MAX_CHARS = 128
PASSWORD_MAX_UTF8_BYTES = 512

ARGON2_TIME_COST = 2
ARGON2_MEMORY_COST_KIB = 19456
ARGON2_PARALLELISM = 1
ARGON2_HASH_LEN = 32
ARGON2_SALT_LEN = 16
ARGON2_VERSION = 19

MAX_CONCURRENT_HASHES = 2

_LEGACY_BCRYPT = re.compile(r"^\$2[abxy]?\$\d{2}\$[./A-Za-z0-9]{53}$")
_SURROGATE = re.compile("[\ud800-\udfff]")

_hasher = PasswordHasher(
    time_cost=ARGON2_TIME_COST,
    memory_cost=ARGON2_MEMORY_COST_KIB,
    parallelism=ARGON2_PARALLELISM,
    hash_len=ARGON2_HASH_LEN,
    salt_len=ARGON2_SALT_LEN,
    encoding="utf-8",
    type=Type.ID,
)
# One queue per process; callers must not hold row locks while awaiting it.
_executor = ThreadPoolExecutor(
    max_workers=MAX_CONCURRENT_HASHES, thread_name_prefix="password-hash"
)
_dummy_hash: str | None = None


class PasswordErrorCode(StrEnum):
    TOO_SHORT = "password_too_short"
    TOO_LONG = "password_too_long"
    INVALID_UNICODE = "password_invalid_unicode"


class PasswordPolicyError(ValueError):
    def __init__(self, code: PasswordErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


class PasswordHashError(RuntimeError):
    """Stored hash is neither valid Argon2 nor recognized legacy bcrypt."""


class VerifyResult(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    LEGACY_BCRYPT = "legacy_bcrypt"


def password_error(password: str, *, new: bool) -> PasswordErrorCode | None:
    """Validate a new password (15–128 chars) or a proof of the current one (1–128)."""
    if len(password) > PASSWORD_MAX_CHARS:
        return PasswordErrorCode.TOO_LONG
    if _SURROGATE.search(password):
        return PasswordErrorCode.INVALID_UNICODE
    if len(password) < (NEW_PASSWORD_MIN_CHARS if new else 1):
        return PasswordErrorCode.TOO_SHORT
    return None


def _require_valid(password: str, *, new: bool) -> None:
    code = password_error(password, new=new)
    if code is not None:
        raise PasswordPolicyError(code)


def is_legacy_bcrypt(stored_hash: str) -> bool:
    return bool(_LEGACY_BCRYPT.match(stored_hash))


def needs_rehash(stored_hash: str) -> bool:
    """True only when the stored Argon2 hash is weaker than current settings.

    Stronger stored parameters are kept, so rolling back settings never downgrades.
    """
    try:
        params = extract_parameters(stored_hash)
    except InvalidHashError as exc:
        raise PasswordHashError("unrecognized password hash format") from exc
    return (
        params.type is not Type.ID
        or params.version < ARGON2_VERSION
        or params.memory_cost < ARGON2_MEMORY_COST_KIB
        or params.time_cost < ARGON2_TIME_COST
        or params.hash_len < ARGON2_HASH_LEN
        or params.salt_len < ARGON2_SALT_LEN
    )


async def _run(fn, *args):
    return await asyncio.get_running_loop().run_in_executor(_executor, fn, *args)


async def hash_new_password(password: str) -> str:
    """Validate a new password and return its Argon2id PHC string."""
    _require_valid(password, new=True)
    return await _run(_hasher.hash, password)


def _verify_sync(stored_hash: str, password: str) -> VerifyResult:
    try:
        _hasher.verify(stored_hash, password)
    except VerifyMismatchError:
        return VerifyResult.MISMATCH
    except (InvalidHashError, VerificationError) as exc:
        logger.warning("password verify failed: unrecognized or corrupt stored hash")
        raise PasswordHashError("unrecognized password hash format") from exc
    return VerifyResult.MATCH


def _dummy_verify_sync(password: str) -> None:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = _hasher.hash(token_urlsafe(24))
    try:
        _hasher.verify(_dummy_hash, password)
    except VerifyMismatchError:
        pass


async def verify_password(password: str, stored_hash: str) -> VerifyResult:
    """Check a proof of the current password against a stored hash.

    Legacy bcrypt does the same Argon2 work as a mismatch and is never accepted.
    """
    _require_valid(password, new=False)
    if is_legacy_bcrypt(stored_hash):
        await _run(_dummy_verify_sync, password)
        return VerifyResult.LEGACY_BCRYPT
    return await _run(_verify_sync, stored_hash, password)


async def dummy_verify(password: str) -> None:
    """Spend the same work as a real verify when there is no usable hash."""
    if password_error(password, new=False) is None:
        await _run(_dummy_verify_sync, password)


def _legacy_verify_sync(password: str, stored_hash: str) -> bool:
    from app.core.security import verify_password as bcrypt_verify

    return bcrypt_verify(password, stored_hash)


async def verify_current_password(password: str, stored_hash: str) -> bool:
    """Proof of the current password for login and password change.

    Transitional until the bcrypt cutoff release (T-001): Argon2 hashes written by reset
    or change are verified here, while recognized bcrypt still uses the old verifier so
    existing accounts keep working. Both run in the shared hashing pool.
    """
    if password_error(password, new=False) is not None:
        return False
    if is_legacy_bcrypt(stored_hash):
        return await _run(_legacy_verify_sync, password, stored_hash)
    return await _run(_verify_sync, stored_hash, password) is VerifyResult.MATCH
