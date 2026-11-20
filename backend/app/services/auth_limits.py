"""Shared auth rate limiter and global mail budget (E-001/F-004/T-003).

PostgreSQL only, so every replica sees the same counters. A rule is a sliding window of
reserved attempts for one HMAC'd subject; raw addresses and IPs are never stored. A
reservation is its own short transaction made before any expensive work and is not
returned when the request later fails. If any rule of one call is full nothing is reserved.
A broken store raises `LimiterUnavailable` (answered 503), never silently allows.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.http_errors import api_error
from app.db import session as db_session
from app.models import AuthRateBucket

logger = logging.getLogger(__name__)

MIN = timedelta(minutes=1)
_DEV_KEY = "local-development-rate-limit-key-0123456789"


@dataclass(frozen=True)
class Rule:
    scope: str
    subject: str
    limit: int
    window: timedelta
    # Log a warning when a reservation reaches this many hits (operator alert at 80%).
    alert_at: int | None = None


class RateLimited(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("rate_limited")
        self.retry_after = retry_after


class LimiterUnavailable(Exception):
    pass


def _key() -> bytes:
    settings = get_settings()
    key = settings.auth_rate_limit_key.strip()
    if not key:
        if settings.is_deployed:
            raise LimiterUnavailable("auth_rate_limit_key is not configured")
        key = _DEV_KEY
    return key.encode("utf-8")


def subject_hash(scope: str, subject: str) -> str:
    return hmac.new(_key(), f"{scope}\0{subject}".encode(), hashlib.sha256).hexdigest()


def client_ip(request: Request) -> str:
    """Socket peer, or the Nth address from the right of X-Forwarded-For behind trusted proxies."""
    peer = request.client.host if request.client else "unknown"
    hops = get_settings().trusted_proxy_hops
    if hops < 1:
        return _normalize_ip(peer)
    parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if len(parts) < hops:
        return _normalize_ip(peer)
    return _normalize_ip(parts[-hops])


def _normalize_ip(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return "unknown"
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        # A /64 is one subscriber; do not let one host rotate through its whole range.
        return str(ipaddress.ip_network(f"{address}/64", strict=False).network_address)
    return str(address)


def _retry_seconds(until: datetime, now: datetime) -> int:
    return max(1, math.ceil((until - now).total_seconds()))


async def reserve(*rules: Rule, now: datetime | None = None) -> None:
    """Reserve one attempt in every rule or raise `RateLimited` without reserving any."""
    if not rules:
        return
    keyed = sorted(
        (((r.scope, subject_hash(r.scope, r.subject)), r) for r in rules), key=lambda item: item[0]
    )
    try:
        async with db_session.async_session_factory() as db:
            now = now or (await db.execute(select(func.now()))).scalar_one()
            for (scope, hashed), rule in keyed:
                await db.execute(
                    pg_insert(AuthRateBucket)
                    .values(scope=scope, subject_hash=hashed, hits=[], expires_at=now + rule.window)
                    .on_conflict_do_nothing()
                )
            buckets = (
                await db.execute(
                    select(AuthRateBucket)
                    .where(
                        AuthRateBucket.scope.in_({k[0] for k, _ in keyed}),
                        AuthRateBucket.subject_hash.in_({k[1] for k, _ in keyed}),
                    )
                    .order_by(AuthRateBucket.scope, AuthRateBucket.subject_hash)
                    .with_for_update()
                )
            ).scalars()
            by_key = {(b.scope, b.subject_hash): b for b in buckets}
            retry_after = 0
            fresh: dict[tuple[str, str], list[datetime]] = {}
            for key, rule in keyed:
                bucket = by_key[key]
                live = sorted(t for t in bucket.hits if t > now - rule.window)
                fresh[key] = live
                if len(live) >= rule.limit:
                    free_at = live[len(live) - rule.limit] + rule.window
                    retry_after = max(retry_after, _retry_seconds(free_at, now))
            if retry_after:
                await db.rollback()
                raise RateLimited(retry_after)
            for key, rule in keyed:
                hits = [*fresh[key], now]
                by_key[key].hits = hits
                by_key[key].expires_at = now + rule.window
                if rule.alert_at is not None and len(hits) == rule.alert_at:
                    logger.warning("auth budget %s reached %s/%s", rule.scope, len(hits), rule.limit)
            await db.commit()
    except (SQLAlchemyError, OSError) as exc:
        logger.exception("auth rate limiter store failed")
        raise LimiterUnavailable from exc


async def count(rule: Rule, *, now: datetime | None = None) -> int:
    """Live reservations of one rule without reserving (global budget checks)."""
    try:
        async with db_session.async_session_factory() as db:
            now = now or (await db.execute(select(func.now()))).scalar_one()
            hits = (
                await db.execute(
                    select(AuthRateBucket.hits).where(
                        AuthRateBucket.scope == rule.scope,
                        AuthRateBucket.subject_hash == subject_hash(rule.scope, rule.subject),
                    )
                )
            ).scalar_one_or_none()
    except (SQLAlchemyError, OSError) as exc:
        logger.exception("auth rate limiter store failed")
        raise LimiterUnavailable from exc
    return sum(1 for t in (hits or []) if t > now - rule.window)


async def enforce(*rules: Rule) -> None:
    """Route helper: 429 with Retry-After, or 503 when the store is unavailable."""
    try:
        await reserve(*rules)
    except RateLimited as exc:
        raise api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except LimiterUnavailable as exc:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_temporarily_unavailable") from exc


async def cleanup_expired(*, limit: int = 100, now: datetime | None = None) -> int:
    """Drop buckets whose last window ended more than 24 h ago."""
    async with db_session.async_session_factory() as db:
        now = now or (await db.execute(select(func.now()))).scalar_one()
        ids = (
            await db.execute(
                select(AuthRateBucket.scope, AuthRateBucket.subject_hash)
                .where(AuthRateBucket.expires_at < now - timedelta(hours=24))
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for scope, hashed in ids:
            await db.execute(
                delete(AuthRateBucket).where(
                    AuthRateBucket.scope == scope, AuthRateBucket.subject_hash == hashed
                )
            )
        await db.commit()
        return len(ids)


# Global send budget of the mail provider's free plan, counted per HTTP attempt.
_DAY = timedelta(hours=24)
_MONTH = timedelta(days=31)


def _budget(scope: str, limit: int, window: timedelta) -> Rule:
    return Rule(scope, "all", limit, window, alert_at=math.ceil(limit * 0.8))


MAIL_BUDGET_ALL = (_budget("mail_send_24h", 90, _DAY), _budget("mail_send_31d", 2700, _MONTH))
MAIL_BUDGET_LINK = (_budget("mail_link_24h", 70, _DAY), _budget("mail_link_31d", 2100, _MONTH))


async def reserve_mail_send(*, link: bool, now: datetime | None = None) -> int | None:
    """Reserve one provider call; returns seconds to wait when the budget is full."""
    rules = MAIL_BUDGET_ALL + (MAIL_BUDGET_LINK if link else ())
    try:
        await reserve(*rules, now=now)
    except RateLimited as exc:
        logger.error("mail send budget exhausted; next free slot in %ss", exc.retry_after)
        return exc.retry_after
    return None


async def link_budget_open(*, now: datetime | None = None) -> bool:
    """Whether a new link mail request may be accepted (ordinary budget not exhausted)."""
    for rule in MAIL_BUDGET_ALL + MAIL_BUDGET_LINK:
        if await count(rule, now=now) >= rule.limit:
            return False
    return True
