"""E-001/F-008/T-001: upgrade z poprzedniego schematu nie zmienia istniejących kont."""

import pytest
from sqlalchemy import select, text

from app.db import session as db_session
from app.db.base import Base
from app.db.migrations import apply_schema
from app.models import User

pytestmark = pytest.mark.pg

_USER_COLUMNS = (
    "email_verified_at",
    "email_revision",
    "credentials_revision",
    "account_status",
    "lifecycle_revision",
    "google_email",
    "google_email_observed_at",
    "restore_recovery_required",
    "accepted_terms_version",
    "accepted_privacy_version",
    "terms_locale",
    "terms_accepted_at",
    "adult_statement_version",
    "adult_confirmed_at",
)
_NEW_TABLES = (
    "account_journal",
    "ai_budget_reservations",
    "ai_budget_periods",
    "ops_alerts",
    "ops_state",
)


async def test_old_schema_upgrades_without_touching_existing_accounts(pg):
    engine = db_session.engine
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE " + ", ".join(_NEW_TABLES) + " CASCADE"))
            await conn.execute(
                text("ALTER TABLE users " + ", ".join(f"DROP COLUMN {c}" for c in _USER_COLUMNS))
            )
            await conn.execute(
                text(
                    "INSERT INTO users (id, email, role, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), 'old@test.com', 'user', now(), now())"
                )
            )
    finally:
        # Restores the schema for the rest of the run even if the setup above fails.
        await apply_schema(engine, Base.metadata)
    # Running it again on the upgraded schema changes nothing.
    await apply_schema(engine, Base.metadata)

    async with pg() as session:
        user = (await session.execute(select(User).where(User.email == "old@test.com"))).scalar_one()
        tables = (
            await session.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_name = ANY(:n)"),
                {"n": list(_NEW_TABLES)},
            )
        ).scalars().all()
    assert sorted(tables) == sorted(_NEW_TABLES)
    assert user.account_status == "active" and user.restore_recovery_required is False
    assert user.email_verified_at is None
    assert user.accepted_terms_version is None and user.terms_accepted_at is None
    assert user.adult_confirmed_at is None and user.google_email is None
