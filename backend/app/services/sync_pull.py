"""POST /sync/pull: pełny profil albo delta względem snapshotu PostgreSQL (E-001/F-003/T-003 pkt 3).

Zmiana jest widoczna w kolejnym delta, gdy jej `sync_xid` nie był widoczny w poprzednim
snapshotcie S. Poprawność nie zależy od zegara, stałego overlap ani ponownego pełnego pull.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http_errors import api_error
from app.db import session as db_session
from app.models import LanguageProfile, LearningCard, SrsState, User, UserSettings, WordList
from app.schemas import (
    SyncCardItem,
    SyncListItem,
    SyncPullResponse,
    SyncSrsState,
    UserSettingsResponse,
)
from app.services.word_lists import ensure_system_list

logger = logging.getLogger(__name__)

CURSOR_VERSION = 1
MAX_CURSOR_CHARS = 8192
TOMBSTONE_RETENTION = timedelta(days=30)
TOMBSTONE_PURGE_BATCH = 500
_ID_CHUNK = 5000
_XID_LIMIT = 2**63
_SNAPSHOT_RE = re.compile(r"^(\d{1,19}):(\d{1,19}):((?:\d{1,19})(?:,\d{1,19})*)?$")
_CURSOR_KEYS = {"v", "e", "u", "p", "s"}

# Parametr przechodzi jako text; asyncpg nie ma kodeka dla pg_snapshot.
_SNAP = "CAST(CAST(:s AS TEXT) AS pg_snapshot)"


def _invalid() -> Exception:
    return api_error(422, "invalid_sync_cursor", "Invalid sync cursor")


def _expired() -> Exception:
    return api_error(410, "sync_cursor_expired", "Sync cursor expired; run a full pull")


def _unavailable() -> Exception:
    return api_error(503, "sync_snapshot_unavailable", "Sync snapshot temporarily unavailable")


def encode_cursor(epoch: str, user_id: UUID, profile_id: UUID, snapshot: str) -> str:
    payload = {"v": CURSOR_VERSION, "e": epoch, "u": str(user_id), "p": str(profile_id), "s": snapshot}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _valid_snapshot(snapshot: object) -> bool:
    if not isinstance(snapshot, str) or len(snapshot) > MAX_CURSOR_CHARS:
        return False
    match = _SNAPSHOT_RE.match(snapshot)
    if match is None:
        return False
    xmin, xmax = int(match.group(1)), int(match.group(2))
    xips = [int(x) for x in match.group(3).split(",")] if match.group(3) else []
    if xmin > xmax or xmax >= _XID_LIMIT:
        return False
    previous = -1
    for xip in xips:
        if xip <= previous or xip < xmin or xip >= xmax:
            return False
        previous = xip
    return True


def decode_cursor(raw: str, user_id: UUID, profile_id: UUID) -> tuple[str, str]:
    """Zwraca (epoch, snapshot); każdy defekt → 422 przed jakimkolwiek zapytaniem SQL."""
    if not raw or len(raw) > MAX_CURSOR_CHARS or not re.fullmatch(r"[A-Za-z0-9_-]+", raw):
        raise _invalid()
    try:
        data = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if not isinstance(data, dict) or set(data) != _CURSOR_KEYS or data["v"] != CURSOR_VERSION:
            raise _invalid()
        epoch = str(UUID(str(data["e"])))
        if UUID(str(data["u"])) != user_id or UUID(str(data["p"])) != profile_id:
            raise _invalid()
        snapshot = data["s"]
    except (ValueError, TypeError, KeyError):
        raise _invalid() from None
    if not _valid_snapshot(snapshot):
        raise _invalid()
    return epoch, snapshot


async def current_epoch(db: AsyncSession) -> str:
    await db.execute(
        text("INSERT INTO sync_epoch (id, epoch) VALUES (1, gen_random_uuid()) ON CONFLICT (id) DO NOTHING")
    )
    return str((await db.execute(text("SELECT epoch FROM sync_epoch WHERE id = 1"))).scalar_one())


def srs_payload(card_id: UUID, state: SrsState, learning_generation: int = 1) -> SyncSrsState:
    return SyncSrsState(
        card_id=card_id,
        status=state.status,
        learning_generation=learning_generation,
        ease=state.ease,
        interval_days=state.interval_days,
        repetitions=state.repetitions,
        lapses=state.lapses,
        next_review_at=state.next_review_at,
        last_reviewed_at=state.last_reviewed_at,
        last_grade=state.last_grade,
        stability=state.stability,
        difficulty=state.difficulty,
        fsrs_step=state.fsrs_step,
    )


def _chunks(ids: list[UUID]):
    for i in range(0, len(ids), _ID_CHUNK):
        yield ids[i : i + _ID_CHUNK]


async def _changed_ids(rr: AsyncSession, table: str, user_id: UUID, profile_id: UUID, snapshot: str):
    result = await rr.execute(
        text(
            f"SELECT id FROM {table} WHERE user_id = :u AND profile_id = :p "
            f"AND sync_xid >= pg_snapshot_xmin({_SNAP}) "
            f"AND NOT pg_visible_in_snapshot(sync_xid, {_SNAP})"
        ),
        {"u": user_id, "p": profile_id, "s": snapshot},
    )
    return list(result.scalars().all())


async def _check_cursor(rr: AsyncSession, user_id: UUID, profile_id: UUID, snapshot: str) -> None:
    row = (
        await rr.execute(
            text(
                f"SELECT pg_snapshot_xmax({_SNAP}) <= pg_snapshot_xmax(pg_current_snapshot()) AS not_future, "
                f"pg_snapshot_xmin({_SNAP}) > COALESCE("
                "(SELECT purged_through_xid FROM profile_sync_state "
                "WHERE user_id = :u AND profile_id = :p), CAST('0' AS xid8)) AS supported"
            ),
            {"u": user_id, "p": profile_id, "s": snapshot},
        )
    ).one()
    if not row.not_future:
        raise _invalid()
    if not row.supported:
        raise _expired()


def card_item(card: LearningCard, state: SrsState | None) -> SyncCardItem:
    return SyncCardItem(
        id=card.id,
        profile_id=card.profile_id,
        deck_id=card.deck_id,
        lemma_l2=card.lemma_l2,
        pos=card.pos,
        gloss_primary=card.gloss_primary,
        content=card.content,
        learning_generation=card.learning_generation,
        enrichment_status=card.enrichment_status,
        content_review_status=card.content_review_status,
        card_activity_status=card.card_activity_status,
        has_content_changes=bool(card.has_content_changes),
        created_at=card.created_at,
        updated_at=card.updated_at,
        srs=srs_payload(card.id, state, card.learning_generation) if state is not None else None,
    )


async def _read_lists(rr: AsyncSession, user_id: UUID, profile_id: UUID) -> list[SyncListItem]:
    lists = (
        await rr.execute(
            select(WordList)
            .where(
                WordList.user_id == user_id,
                WordList.profile_id == profile_id,
                WordList.deleted_at.is_(None),
            )
            .order_by(WordList.is_system.desc(), WordList.created_at.asc())
        )
    ).scalars().all()
    counts = dict(
        (
            await rr.execute(
                select(LearningCard.deck_id, func.count())
                .where(
                    LearningCard.user_id == user_id,
                    LearningCard.profile_id == profile_id,
                    LearningCard.deleted_at.is_(None),
                )
                .group_by(LearningCard.deck_id)
            )
        ).all()
    )
    return [
        SyncListItem(
            id=wl.id,
            name=wl.name,
            is_system=wl.is_system,
            is_pending_inbox=bool(wl.is_pending_inbox),
            word_count=int(counts.get(None if wl.is_system else wl.id, 0)),
            created_at=wl.created_at,
        )
        for wl in lists
    ]


async def _read_snapshot(
    user_id: UUID, profile_id: UUID, epoch: str, cursor: tuple[str, str] | None
) -> SyncPullResponse:
    async with db_session.async_session_factory() as rr:
        await rr.connection(
            execution_options={"isolation_level": "REPEATABLE READ", "postgresql_readonly": True}
        )
        snapshot = (await rr.execute(text("SELECT CAST(pg_current_snapshot() AS TEXT)"))).scalar_one()
        new_cursor = encode_cursor(epoch, user_id, profile_id, snapshot)
        if len(new_cursor) > MAX_CURSOR_CHARS:
            raise _unavailable()

        deleted_cards: set[UUID] = set()
        deleted_lists: set[UUID] = set()
        card_ids: list[UUID] | None = None
        if cursor is not None:
            cursor_epoch, since = cursor
            if cursor_epoch != epoch:
                raise _expired()
            await _check_cursor(rr, user_id, profile_id, since)
            card_ids = await _changed_ids(rr, "learning_cards", user_id, profile_id, since)
            list_ids = await _changed_ids(rr, "word_lists", user_id, profile_id, since)
            tombstones = await rr.execute(
                text(
                    "SELECT entity_type, entity_id FROM sync_tombstones "
                    "WHERE user_id = :u AND profile_id = :p "
                    f"AND sync_xid >= pg_snapshot_xmin({_SNAP}) "
                    f"AND NOT pg_visible_in_snapshot(sync_xid, {_SNAP})"
                ),
                {"u": user_id, "p": profile_id, "s": since},
            )
            for kind, entity_id in tombstones.all():
                (deleted_cards if kind == "card" else deleted_lists).add(entity_id)
            for chunk in _chunks(list_ids):
                gone = await rr.execute(
                    select(WordList.id).where(WordList.id.in_(chunk), WordList.deleted_at.is_not(None))
                )
                deleted_lists.update(gone.scalars().all())

        card_query = (
            select(LearningCard, SrsState)
            .outerjoin(SrsState, (SrsState.card_id == LearningCard.id) & (SrsState.scope == "main"))
            .where(LearningCard.user_id == user_id, LearningCard.profile_id == profile_id)
        )
        rows: list = []
        if card_ids is None:
            rows = (await rr.execute(card_query.where(LearningCard.deleted_at.is_(None)))).all()
        else:
            for chunk in _chunks(card_ids):
                rows.extend((await rr.execute(card_query.where(LearningCard.id.in_(chunk)))).all())

        cards: list[SyncCardItem] = []
        for card, state in rows:
            if card.deleted_at is not None:
                deleted_cards.add(card.id)
            else:
                cards.append(card_item(card, state))
        live_ids = {c.id for c in cards}
        deleted_cards -= live_ids

        settings = (
            await rr.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        ).scalar_one()
        lists = await _read_lists(rr, user_id, profile_id)
        deleted_lists -= {item.id for item in lists}
        return SyncPullResponse(
            server_time=datetime.now(UTC),
            settings=UserSettingsResponse.model_validate(settings),
            cards=cards,
            lists=lists,
            deleted_card_ids=sorted(deleted_cards, key=str),
            deleted_list_ids=sorted(deleted_lists, key=str),
            cursor=new_cursor,
        )


async def pull(db: AsyncSession, user: User, profile_id: UUID, raw_cursor: str | None) -> SyncPullResponse:
    user_id = user.id
    cursor = decode_cursor(raw_cursor, user_id, profile_id) if raw_cursor else None

    profile = (
        await db.execute(
            select(LanguageProfile.id).where(
                LanguageProfile.id == profile_id, LanguageProfile.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if profile is None:
        raise api_error(404, "profile_not_found", "Profile not found")

    # Przygotowanie (ustawienia, lista systemowa, epoch) kończy własną transakcję przed snapshotem.
    settings = (await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))).scalar_one_or_none()
    if settings is None:
        db.add(UserSettings(user_id=user_id))
        await db.flush()
    await ensure_system_list(db, user_id, profile_id)
    epoch = await current_epoch(db)
    await db.commit()

    try:
        return await _read_snapshot(user_id, profile_id, epoch, cursor)
    except DBAPIError:
        logger.exception("sync snapshot unavailable")
        raise _unavailable() from None


async def purge_sync_tombstones(*, now: datetime | None = None, limit: int = TOMBSTONE_PURGE_BATCH) -> int:
    """Usuwa tombstones starsze niż 30 dni i w tej samej transakcji podnosi horyzont kursora profilu."""
    cutoff = (now or datetime.now(UTC)) - TOMBSTONE_RETENTION
    async with db_session.async_session_factory() as db:
        result = await db.execute(
            text(
                "WITH doomed AS (SELECT id, user_id, profile_id, sync_xid FROM sync_tombstones "
                "WHERE created_at < :cutoff ORDER BY created_at LIMIT :n FOR UPDATE SKIP LOCKED), "
                "bump AS (INSERT INTO profile_sync_state (user_id, profile_id, purged_through_xid) "
                "SELECT DISTINCT ON (user_id, profile_id) user_id, profile_id, sync_xid FROM doomed "
                "ORDER BY user_id, profile_id, sync_xid DESC "
                "ON CONFLICT (user_id, profile_id) DO UPDATE SET purged_through_xid = "
                "GREATEST(profile_sync_state.purged_through_xid, EXCLUDED.purged_through_xid)), "
                "gone AS (DELETE FROM sync_tombstones WHERE id IN (SELECT id FROM doomed) RETURNING 1) "
                "SELECT count(*) FROM gone"
            ),
            {"cutoff": cutoff, "n": limit},
        )
        removed = int(result.scalar_one())
        await db.commit()
        return removed
