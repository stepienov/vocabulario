"""E-001/F-006/T-002: wniosek o usunięcie konta, cofnięcie, bariera zapisów i purge."""

import secrets
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import now_utc
from app.db.lifecycle import LifecycleBlocked
from app.models import (
    AccountDeletion,
    AppLog,
    LearningCard,
    LexicalEntry,
    LlmUsage,
    LookupEvent,
    User,
)
from app.services.account_purge import run_purge_cycle
from tests.pg_factories import create_card, create_profile
from tests.test_account_recovery import (
    PASSWORD,
    _bearer,
    _code,
    _login,
    _outbox,
    _register,
    _user,
)

pytestmark = pytest.mark.pg

API = "/api/v1/account-deletion"


@pytest.fixture(autouse=True)
def _deletion_enabled(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "account_deletion_enabled", True)
    monkeypatch.setattr(settings, "account_erasure_key", "k" * 48)
    monkeypatch.setattr(settings, "account_erasure_key_version", 1)


async def _verified(pg, client) -> tuple[str, dict]:
    email = f"del-{uuid4()}@test.com"
    tokens = await _register(client, email)
    async with pg() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.email_verified_at = now_utc()
        await db.commit()
    return email, tokens


async def _proof(client, email: str, action: str, password: str = PASSWORD):
    return await client.post(
        f"{API}/proof/password",
        json={"email": email, "password": password, "action": action},
    )


async def _ask(client, email: str, request_id=None, secret=None):
    proof = await _proof(client, email, "request")
    assert proof.status_code == 200, proof.text
    assert proof.headers["cache-control"] == "no-store"
    rid, secret = request_id or uuid4(), secret or secrets.token_urlsafe(32)
    response = await client.post(
        f"{API}/request",
        json={
            "request_id": str(rid),
            "action_token": proof.json()["action_token"],
            "status_secret": secret,
            "confirmation_version": "delete-account-v1",
        },
    )
    return response, rid, secret


async def _cancel(client, email: str, deletion_id, request_id=None):
    proof = await _proof(client, email, "cancel")
    assert proof.status_code == 200, proof.text
    return await client.post(
        f"{API}/cancel",
        json={
            "deletion_id": str(deletion_id),
            "request_id": str(request_id or uuid4()),
            "action_token": proof.json()["action_token"],
        },
    )


async def _deletion(pg, deletion_id) -> AccountDeletion:
    async with pg() as db:
        return (
            await db.execute(select(AccountDeletion).where(AccountDeletion.id == deletion_id))
        ).scalar_one()


async def test_request_blocks_account_and_is_idempotent(pg, pg_client):
    email, tokens = await _verified(pg, pg_client)
    before = await _user(pg, email)

    response, rid, secret = await _ask(pg_client, email)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["state"] == "grace" and body["can_cancel"] is True
    assert body["deletion_id"] == str(rid)
    deletion = await _deletion(pg, rid)
    assert deletion.cancel_until - deletion.requested_at == timedelta(hours=168)
    assert deletion.purge_due_at - deletion.requested_at == timedelta(days=14)

    after = await _user(pg, email)
    assert after.account_status == "deletion_pending"
    assert after.lifecycle_revision == before.lifecycle_revision + 1

    me = await pg_client.get("/api/v1/me", headers=_bearer(tokens))
    assert (me.status_code, _code(me)) == (403, "account_deletion_pending")
    login = await _login(pg_client, email, PASSWORD)
    assert (login.status_code, _code(login)) == (403, "account_deletion_pending")
    [mail] = await _outbox(pg, "account_deletion_started")
    assert mail.user_id == before.id

    # exact retry returns the same process; another secret under the same id is a conflict
    again, _, _ = await _ask(pg_client, email, request_id=rid, secret=secret)
    assert again.status_code == 202 and again.json()["deletion_id"] == str(rid)
    clash, _, _ = await _ask(pg_client, email, request_id=rid)
    assert (clash.status_code, _code(clash)) == (409, "operation_id_conflict")
    assert len(await _outbox(pg, "account_deletion_started")) == 1

    status = await pg_client.post(
        f"{API}/status", json={"request_id": str(rid), "status_secret": secret}
    )
    assert status.status_code == 200 and status.json()["state"] == "grace"
    assert status.headers["cache-control"] == "no-store"
    wrong = await pg_client.post(
        f"{API}/status",
        json={"request_id": str(rid), "status_secret": secrets.token_urlsafe(32)},
    )
    assert (wrong.status_code, _code(wrong)) == (404, "deletion_not_found")


async def test_proof_is_neutral_and_disabled_flag_refuses(pg, pg_client, monkeypatch):
    email, _ = await _verified(pg, pg_client)
    bad = await _proof(pg_client, email, "request", password="not the password")
    ghost = await _proof(pg_client, f"ghost-{uuid4()}@test.com", "request")
    assert bad.status_code == ghost.status_code == 401
    assert bad.json() == ghost.json()

    monkeypatch.setattr(get_settings(), "account_deletion_enabled", False)
    off = await _proof(pg_client, email, "request")
    assert (off.status_code, _code(off)) == (503, "account_deletion_unavailable")
    assert (await _user(pg, email)).account_status == "active"


async def test_cancel_restores_same_user_without_old_sessions(pg, pg_client):
    email, tokens = await _verified(pg, pg_client)
    before = await _user(pg, email)
    response, rid, _ = await _ask(pg_client, email)
    assert response.status_code == 202

    cancelled = await _cancel(pg_client, email, rid)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["requires_login"] is True
    assert cancelled.json()["deletion"]["state"] == "cancelled"
    assert (await _deletion(pg, rid)).state == "cancelled"

    after = await _user(pg, email)
    assert after.id == before.id and after.account_status == "active"
    me = await pg_client.get("/api/v1/me", headers=_bearer(tokens))
    assert me.status_code == 401
    login = await _login(pg_client, email, PASSWORD)
    assert login.status_code == 200, login.text
    assert len(await _outbox(pg, "account_deletion_cancelled")) == 1

    # a second cancel has nothing left to cancel and must not queue another mail
    again = await _proof(pg_client, email, "cancel")
    assert (again.status_code, _code(again)) == (409, "no_pending_deletion")
    assert len(await _outbox(pg, "account_deletion_cancelled")) == 1


async def test_cancel_after_window_is_irreversible(pg, pg_client):
    email, _ = await _verified(pg, pg_client)
    response, rid, _ = await _ask(pg_client, email)
    assert response.status_code == 202
    async with pg() as db:
        row = (
            await db.execute(select(AccountDeletion).where(AccountDeletion.id == rid))
        ).scalar_one()
        row.cancel_until = now_utc() - timedelta(seconds=1)
        await db.commit()
    late = await _proof(pg_client, email, "cancel")
    assert (late.status_code, _code(late)) == (409, "deletion_irreversible")


async def test_lifecycle_barrier_rejects_stale_writers(pg, pg_client):
    email, _ = await _verified(pg, pg_client)
    user = await _user(pg, email)
    async with pg() as db:
        profile = await create_profile(db, user, "pl", "en")
        card = await create_card(db, profile, "house", "noun")
        await db.commit()
        card_id = card.id
    response, _, _ = await _ask(pg_client, email)
    assert response.status_code == 202

    async with pg() as db:
        card = await db.get(LearningCard, card_id)
        card.lemma_l2 = "changed"
        with pytest.raises(LifecycleBlocked):
            await db.flush()
        await db.rollback()
    async with pg() as db:
        assert (await db.get(LearningCard, card_id)).lemma_l2 == "house"


async def test_purge_removes_only_the_owner_and_leaves_a_marker(pg, pg_client):
    email, tokens = await _verified(pg, pg_client)
    other_email, other_tokens = await _verified(pg, pg_client)
    user, other = await _user(pg, email), await _user(pg, other_email)
    async with pg() as db:
        profile = await create_profile(db, user, "pl", "en")
        other_profile = await create_profile(db, other, "pl", "en")
        await create_card(db, profile, "house", "noun")
        await create_card(db, other_profile, "tree", "noun")
        db.add(
            LexicalEntry(
                lang_pair="en-pl",
                lemma_l2="shared",
                pos="noun",
                content={},
                created_by_user_id=user.id,
            )
        )
        db.add(AppLog(level="info", category="http", event="mine", status="ok", user_id=user.id))
        db.add(AppLog(level="info", category="http", event="theirs", status="ok", user_id=other.id))
        db.add(
            LookupEvent(
                user_id=user.id,
                profile_id=profile.id,
                query="house",
                query_norm="house",
                source="lookup",
                candidate_count=0,
                http_status=200,
                candidates=[],
                ai_complete=False,
            )
        )
        db.add(LlmUsage(user_id=user.id, purpose="enrich", model="m", status="ok"))
        await db.commit()

    response, rid, secret = await _ask(pg_client, email)
    assert response.status_code == 202
    async with pg() as db:
        row = (
            await db.execute(select(AccountDeletion).where(AccountDeletion.id == rid))
        ).scalar_one()
        row.cancel_until = now_utc() - timedelta(minutes=1)
        await db.commit()

    assert await run_purge_cycle(now_utc()) >= 1
    for _ in range(3):
        if (await _deletion(pg, rid)).state == "completed":
            break
        await run_purge_cycle(now_utc())
    done = await _deletion(pg, rid)
    assert done.state == "completed" and done.completed_at is not None
    assert done.user_id is None

    async with pg() as db:
        assert await db.get(User, user.id) is None
        assert await db.get(User, other.id) is not None
        for model, column in (
            (LearningCard, LearningCard.user_id),
            (LookupEvent, LookupEvent.user_id),
            (LlmUsage, LlmUsage.user_id),
        ):
            owned = (
                await db.execute(select(func.count()).select_from(model).where(column == user.id))
            ).scalar_one()
            assert owned == 0, model.__name__
        mine = (
            await db.execute(select(func.count()).select_from(AppLog).where(AppLog.user_id == user.id))
        ).scalar_one()
        theirs = (
            await db.execute(
                select(func.count()).select_from(AppLog).where(AppLog.user_id == other.id)
            )
        ).scalar_one()
        assert (mine, theirs) == (0, 1)
        shared = (
            await db.execute(select(LexicalEntry).where(LexicalEntry.lemma_l2 == "shared"))
        ).scalar_one()
        assert shared.created_by_user_id is None
        survivors = (
            await db.execute(select(func.count()).select_from(LearningCard))
        ).scalar_one()
        assert survivors == 1

    # the old session is told the account is gone, the neighbour keeps working
    gone = await pg_client.get("/api/v1/me", headers=_bearer(tokens))
    assert (gone.status_code, _code(gone)) == (401, "account_deleted")
    ok = await pg_client.get("/api/v1/me", headers=_bearer(other_tokens))
    assert ok.status_code == 200

    status = await pg_client.post(
        f"{API}/status", json={"request_id": str(rid), "status_secret": secret}
    )
    assert status.status_code == 200 and status.json()["state"] == "completed"
    assert (await _login(pg_client, email, PASSWORD)).status_code == 401

    # running the worker again is harmless
    assert await run_purge_cycle(now_utc()) == 0
