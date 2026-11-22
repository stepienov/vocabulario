import asyncio
import threading
import time

import pytest
from argon2 import PasswordHasher
from passlib.hash import bcrypt

from app.core import passwords
from app.core.passwords import (
    PasswordErrorCode,
    PasswordHashError,
    PasswordPolicyError,
    VerifyResult,
    hash_new_password,
    needs_rehash,
    password_error,
    verify_password,
)

NON_BMP = "\U0001f600"


@pytest.mark.parametrize(
    ("password", "new", "expected"),
    [
        ("a" * 14, True, PasswordErrorCode.TOO_SHORT),
        ("a" * 15, True, None),
        ("a" * 128, True, None),
        ("a" * 129, True, PasswordErrorCode.TOO_LONG),
        # 14 ASCII + one non-BMP char is 15 characters, although 16 UTF-16 units.
        ("a" * 14 + NON_BMP, True, None),
        ("a" * 13 + NON_BMP, True, PasswordErrorCode.TOO_SHORT),
        (NON_BMP * 128, True, None),
        (" " * 15, True, None),
        ("  spaces kept  ", True, None),
        ("a" * 20 + "\ud800", True, PasswordErrorCode.INVALID_UNICODE),
        ("\udfff" + "a" * 20, False, PasswordErrorCode.INVALID_UNICODE),
        ("", False, PasswordErrorCode.TOO_SHORT),
        ("x", False, None),
        ("a" * 14, False, None),
        ("a" * 129, False, PasswordErrorCode.TOO_LONG),
    ],
)
def test_password_error_counts_unicode_scalar_values(password, new, expected):
    assert password_error(password, new=new) == expected


async def test_invalid_password_is_rejected_before_hashing(monkeypatch):
    def fail(*_):
        raise AssertionError("hasher must not run")

    monkeypatch.setattr(passwords, "_run", fail)
    with pytest.raises(PasswordPolicyError) as exc:
        await hash_new_password("a" * 14)
    assert exc.value.code is PasswordErrorCode.TOO_SHORT
    with pytest.raises(PasswordPolicyError):
        await verify_password("a" * 129, "$argon2id$irrelevant")


async def test_hash_uses_explicit_argon2id_parameters_and_fresh_salt():
    password = NON_BMP * 128
    first = await hash_new_password(password)
    second = await hash_new_password(password)
    assert first.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert first != second
    assert len(first) <= 255
    assert not needs_rehash(first)
    assert await verify_password(password, first) is VerifyResult.MATCH


async def test_password_is_not_truncated_or_normalized():
    prefix = "x" * 72
    stored = await hash_new_password(prefix + "-first")
    assert await verify_password(prefix + "-second", stored) is VerifyResult.MISMATCH

    # 70 ASCII bytes + a 4-byte char crosses the 72-byte boundary.
    unicode_stored = await hash_new_password("y" * 70 + NON_BMP + "a")
    assert await verify_password("y" * 70 + NON_BMP + "b", unicode_stored) is VerifyResult.MISMATCH

    composed = await hash_new_password("caf\u00e9 long password")
    assert await verify_password("cafe\u0301 long password", composed) is VerifyResult.MISMATCH

    spaced = await hash_new_password(" padded password ")
    assert await verify_password("padded password", spaced) is VerifyResult.MISMATCH
    assert await verify_password(" padded password ", spaced) is VerifyResult.MATCH


async def test_legacy_bcrypt_is_recognized_but_never_accepted():
    legacy = bcrypt.using(rounds=4).hash("correct legacy password")
    assert await verify_password("correct legacy password", legacy) is VerifyResult.LEGACY_BCRYPT


@pytest.mark.parametrize(
    "stored",
    [
        "plain-text-password",
        "$argon2id$v=19$m=19456,t=2,p=1$broken",
        "$pbkdf2-sha256$29000$abc$def",
    ],
)
async def test_unknown_or_corrupt_hash_is_an_operational_error(stored, caplog):
    secret = "Distinctive-Secret-Value-123"
    with pytest.raises(PasswordHashError):
        await verify_password(secret, stored)
    assert secret not in caplog.text
    assert stored not in caplog.text


def test_needs_rehash_upgrades_weaker_hashes_but_never_downgrades():
    weaker = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash("p" * 15)
    stronger = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4).hash("p" * 15)
    argon2i = PasswordHasher(
        time_cost=2, memory_cost=19456, parallelism=1, type=passwords.Type.I
    ).hash("p" * 15)
    assert needs_rehash(weaker)
    assert needs_rehash(argon2i)
    assert not needs_rehash(stronger)
    with pytest.raises(PasswordHashError):
        needs_rehash(bcrypt.using(rounds=4).hash("p"))


async def test_hashing_runs_off_the_event_loop_at_most_two_at_a_time(monkeypatch):
    active = 0
    peak = 0
    lock = threading.Lock()
    loop_thread = threading.get_ident()

    class SlowHasher:
        def hash(self, password):
            nonlocal active, peak
            assert threading.get_ident() != loop_thread
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            return "hashed"

    monkeypatch.setattr(passwords, "_hasher", SlowHasher())
    results = await asyncio.gather(*(hash_new_password("p" * 15) for _ in range(6)))
    assert results == ["hashed"] * 6
    assert peak == passwords.MAX_CONCURRENT_HASHES
