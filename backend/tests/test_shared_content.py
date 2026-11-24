from __future__ import annotations

from uuid import uuid4

import pytest

from app.ai.schemas.similar_words import MIN_SIMILAR_FOR_QUIZ
from app.models import LearningCard, LexicalEntry


def _complete_content(gloss: str) -> dict:
    return {
        "schema_version": "vocabulario.card.v1",
        "lemma": "la parada",
        "language": "es",
        "pos": "noun",
        "meanings": [{"gloss_l1": gloss, "examples": [{"l2": "a", "l1": "b"}]}],
        "similar_words": [
            {"lemma": f"la palabra {i}", "pos": "noun", "gloss_l1": f"słowo {i}"}
            for i in range(MIN_SIMILAR_FOR_QUIZ)
        ],
        "inflection": {
            "verbs": None,
            "nouns": {"singular": "la parada", "plural": "las paradas"},
            "adjectives": None,
        },
        "word_family_l2": [],
    }


def test_linked_cards_read_and_write_the_shared_content():
    entry = LexicalEntry(
        lang_pair="pl>es",
        lemma_l2="la parada",
        pos="noun",
        content={"lemma": "la parada", "meanings": []},
    )
    first = LearningCard(
        id=uuid4(),
        user_id=uuid4(),
        profile_id=uuid4(),
        lemma_l2="la parada",
        pos="noun",
        lexical_entry=entry,
        content=entry.content,
    )
    second = LearningCard(
        id=uuid4(),
        user_id=uuid4(),
        profile_id=uuid4(),
        lemma_l2="la parada",
        pos="noun",
        lexical_entry=entry,
        content=entry.content,
    )

    assert first._content is None
    assert second._content is None
    first.content = {"lemma": "la parada", "meanings": [{"gloss_l1": "przystanek"}]}
    assert second.content["meanings"][0]["gloss_l1"] == "przystanek"
    assert second._content is None


def test_linked_legacy_snapshot_is_not_replaced_or_published():
    from app.services.card_jobs import _apply_content_fields

    entry = LexicalEntry(
        lang_pair="pl>es",
        lemma_l2="la parada",
        pos="noun",
        content={"lemma": "la parada", "meanings": [{"gloss_l1": "przystanek"}]},
        learning_generation=2,
    )
    card = LearningCard(
        id=uuid4(),
        user_id=uuid4(),
        profile_id=uuid4(),
        lemma_l2="la parada",
        pos="noun",
        content={"lemma": "la parada", "meanings": [{"gloss_l1": "postój"}]},
    )
    card.lexical_entry = entry

    assert card.content["meanings"][0]["gloss_l1"] == "postój"
    assert card.learning_generation == 1
    card.content = {"lemma": "la parada", "meanings": [{"gloss_l1": "przerwa"}]}
    assert entry.content["meanings"][0]["gloss_l1"] == "przystanek"
    assert card.content["meanings"][0]["gloss_l1"] == "przerwa"
    _apply_content_fields(
        card, {"lemma": "la parada", "meanings": [{"gloss_l1": "zatrzymanie"}]}
    )
    assert entry.content["meanings"][0]["gloss_l1"] == "przystanek"
    assert card.content["meanings"][0]["gloss_l1"] == "zatrzymanie"


@pytest.mark.pg
@pytest.mark.parametrize("path", ["cache", "enrichment"])
async def test_new_shared_card_removes_its_working_content(pg, path):
    from sqlalchemy import select

    from app.services.card_jobs import _persist_enrichment_result, hydrate_from_lexical_cache
    from tests.pg_factories import create_card, create_profile, create_user

    content = _complete_content("przystanek")

    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        entry = LexicalEntry(
            lang_pair="pl>es",
            lemma_l2="la parada",
            pos="noun",
            content=content,
        )
        db.add(entry)
        await db.flush()
        card = await create_card(
            db, profile, "la parada", "noun", status="pending", content=content
        )
        if path == "cache":
            card.lexical_entry_id = entry.id
            assert await hydrate_from_lexical_cache(db, card, profile)
        else:
            await _persist_enrichment_result(
                db, card, profile, content, entry=entry, notified=True
            )
        await db.commit()
        card_id, entry_id = card.id, entry.id

    async with pg() as db:
        stored = await db.get(LearningCard, card_id)
        assert stored.lexical_entry_id == entry_id
        assert stored.enrichment_status == "ready"
        assert stored.content["meanings"][0]["gloss_l1"] == "przystanek"
        assert await db.scalar(
            select(LearningCard._content.is_(None)).where(LearningCard.id == card_id)
        )


@pytest.mark.pg
@pytest.mark.parametrize("invalid", ["other_pair", "incomplete", "content_headword"])
async def test_cache_hydration_does_not_share_an_invalid_pinned_entry(pg, invalid):
    from app.services.card_jobs import hydrate_from_lexical_cache
    from tests.pg_factories import create_card, create_profile, create_user

    working = {"lemma": "la parada", "meanings": [], "examples_pending": True}
    content = _complete_content("stop")
    if invalid == "incomplete":
        content["meanings"] = [{"gloss_l1": "stop", "examples": []}]
    if invalid == "content_headword":
        content["lemma"] = "otra"
    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        entry = LexicalEntry(
            lang_pair="en>es" if invalid == "other_pair" else "pl>es",
            lemma_l2="la parada",
            pos="noun",
            content=content,
        )
        db.add(entry)
        await db.flush()
        card = await create_card(
            db, profile, "la parada", "noun", status="pending", content=working
        )
        card.lexical_entry_id = entry.id
        await db.flush()

        assert not await hydrate_from_lexical_cache(db, card, profile)
        assert card.lexical_entry_id is None
        assert card.content == working
        assert card.enrichment_status == "pending"
        assert entry.usage_count == 0


@pytest.mark.pg
async def test_enrichment_does_not_share_an_entry_matching_only_the_l1_gloss(pg):
    from app.services.card_jobs import _persist_enrichment_result, apply_lexical_keys
    from tests.pg_factories import create_card, create_profile, create_user

    content = _complete_content("przystanek")
    other_content = _complete_content("parada")
    other_content["lemma"] = "el sombrero"
    other_content["inflection"]["nouns"] = {"singular": "el sombrero", "plural": "los sombreros"}
    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        other = LexicalEntry(
            lang_pair="pl>es",
            lemma_l2="el sombrero",
            lemma_l1_primary="parada",
            pos="noun",
            content=other_content,
        )
        apply_lexical_keys(other)
        db.add(other)
        await db.flush()
        card = await create_card(db, profile, "la parada", "noun", status="pending", content=content)

        await _persist_enrichment_result(db, card, profile, content, entry=None, notified=True)

        assert card.lexical_entry_id != other.id
        assert card.content["lemma"] == "la parada"


@pytest.mark.pg
@pytest.mark.parametrize(
    ("lemma", "pinned", "expected"),
    [
        ("la cura", "el cura", "la cura"),
        ("cura", None, None),
        ("la cura", None, "la cura"),
    ],
)
async def test_cache_hydration_does_not_merge_ambiguous_gendered_headwords(
    pg, lemma, pinned, expected
):
    from app.services.card_jobs import apply_lexical_keys, hydrate_from_lexical_cache
    from tests.pg_factories import create_card, create_profile, create_user

    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        entries = {}
        for headword in ("el cura", "la cura"):
            content = _complete_content(headword)
            content["lemma"] = headword
            content["inflection"]["nouns"] = {"singular": headword, "plural": headword}
            entry = LexicalEntry(lang_pair="pl>es", lemma_l2=headword, pos="noun", content=content)
            apply_lexical_keys(entry)
            db.add(entry)
            entries[headword] = entry
        await db.flush()
        working = {"lemma": lemma, "meanings": [], "examples_pending": True}
        card = await create_card(db, profile, lemma, "noun", status="pending", content=working)
        if pinned:
            card.lexical_entry_id = entries[pinned].id
            await db.flush()

        assert await hydrate_from_lexical_cache(db, card, profile) is (expected is not None)
        if expected is None:
            assert card.lexical_entry_id is None
            assert card.content == working
        else:
            assert card.lexical_entry_id == entries[expected].id
            assert card.content["lemma"] == expected


@pytest.mark.pg
async def test_stale_family_projection_cannot_overwrite_a_published_correction(pg):
    from sqlalchemy.orm.exc import StaleDataError

    from app.models import LanguageProfile
    from app.services.shared_content import content_revision, publish_lexical_content
    from app.services.word_families import sync_word_family
    from tests.pg_factories import create_profile, create_user

    original = _complete_content("postój")
    corrected = _complete_content("przystanek")
    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        entry = LexicalEntry(
            lang_pair="pl>es", lemma_l2="la parada", pos="noun", content=original
        )
        db.add(entry)
        await db.commit()
        profile_id, entry_id = profile.id, entry.id

    async with pg() as stale_db, pg() as publisher:
        stale_entry = await stale_db.get(LexicalEntry, entry_id)
        stale_profile = await stale_db.get(LanguageProfile, profile_id)
        await publish_lexical_content(
            publisher,
            entry_id=entry_id,
            expected_generation=1,
            expected_content_revision=content_revision(original),
            content=corrected,
            learning_impact=True,
        )
        await publisher.commit()
        with pytest.raises(StaleDataError):
            await sync_word_family(stale_db, stale_profile, dict(stale_entry.content), stale_entry)
            await stale_db.flush()
        await stale_db.rollback()

    async with pg() as db:
        stored = await db.get(LexicalEntry, entry_id)
        assert stored.content["meanings"][0]["gloss_l1"] == "przystanek"
        assert stored.learning_generation == 2


@pytest.mark.pg
async def test_manual_shared_learning_correction_resets_all_owners_and_rejects_stale_reviews(
    pg, pg_client
):
    from sqlalchemy import select

    from app.models import ReviewLog, SrsState
    from app.schemas import SyncReviewItem
    from app.api.v1.sync import legacy_review_fingerprint
    from app.services.shared_content import content_revision, publish_lexical_content
    from tests.pg_factories import auth_headers, create_profile, create_user

    async with pg() as db:
        user_a = await create_user(db)
        profile_a = await create_profile(db, user_a, "pl", "es")
        user_b = await create_user(db)
        profile_b = await create_profile(db, user_b, "pl", "es")
        entry = LexicalEntry(
            lang_pair="pl>es",
            lemma_l2="la parada",
            lemma_l1_primary="postój",
            pos="noun",
            content=_complete_content("postój"),
        )
        db.add(entry)
        await db.flush()
        entry_id = entry.id
        card_a = LearningCard(
            user_id=user_a.id,
            profile_id=profile_a.id,
            lexical_entry=entry,
            lemma_l2="la parada",
            pos="noun",
            gloss_primary="postój",
            content=entry.content,
            enrichment_status="ready",
        )
        card_b = LearningCard(
            user_id=user_b.id,
            profile_id=profile_b.id,
            lexical_entry=entry,
            lemma_l2="la parada",
            pos="noun",
            gloss_primary="postój",
            content=entry.content,
            enrichment_status="ready",
        )
        db.add_all([card_a, card_b])
        await db.flush()
        db.add_all(
            [
                SrsState(
                    card_id=card_a.id,
                    scope="main",
                    status="review",
                    repetitions=4,
                    interval_days=8,
                ),
                SrsState(
                    card_id=card_b.id,
                    scope="main",
                    status="learning",
                    repetitions=2,
                    interval_days=1,
                ),
                ReviewLog(
                    card_id=card_a.id,
                    user_id=user_a.id,
                    grade="good",
                    mode="flip",
                    correct=True,
                ),
            ]
        )
        legacy_review = SyncReviewItem.model_validate(
            {
                "client_id": str(uuid4()),
                "card_id": str(card_a.id),
                "grade": "good",
                "mode": "flip",
                "direction": "l2_l1",
                "correct": True,
                "reviewed_at": "2026-11-24T10:00:00Z",
            }
        )
        db.add(
            ReviewLog(
                client_id=legacy_review.client_id,
                card_id=card_a.id,
                user_id=user_a.id,
                grade=legacy_review.grade,
                mode=legacy_review.mode,
                direction=legacy_review.direction,
                correct=legacy_review.correct,
                reviewed_at=legacy_review.reviewed_at,
                intent_fingerprint=legacy_review_fingerprint(legacy_review),
            )
        )
        headers_a = await auth_headers(db, user_a)
        headers_b = await auth_headers(db, user_b)

    first_a = (
        await pg_client.post(
            "/api/v1/sync/pull",
            json={"profile_id": str(profile_a.id), "cursor": None},
            headers=headers_a,
        )
    ).json()
    first_b = (
        await pg_client.post(
            "/api/v1/sync/pull",
            json={"profile_id": str(profile_b.id), "cursor": None},
            headers=headers_b,
        )
    ).json()
    assert first_a["cards"][0]["content"]["meanings"][0]["gloss_l1"] == "postój"
    assert first_a["cards"][0]["learning_generation"] == 1
    legacy_replay = (
        await pg_client.post(
            "/api/v1/sync/push",
            json={
                "reviews": [
                    {
                        "client_id": str(legacy_review.client_id),
                        "card_id": str(card_a.id),
                        "grade": "good",
                        "mode": "flip",
                        "direction": "l2_l1",
                        "correct": True,
                        "reviewed_at": "2026-11-24T10:00:00Z",
                        "learning_generation": 1,
                    }
                ]
            },
            headers=headers_a,
        )
    ).json()
    assert legacy_replay["review_results"][0]["outcome"] == "duplicate"

    async with pg() as db:
        await publish_lexical_content(
            db,
            entry_id=entry_id,
            expected_generation=1,
            expected_content_revision=content_revision(_complete_content("postój")),
            content=_complete_content("przystanek"),
            learning_impact=True,
        )
        await db.commit()

    delta_a = (
        await pg_client.post(
            "/api/v1/sync/pull",
            json={"profile_id": str(profile_a.id), "cursor": first_a["cursor"]},
            headers=headers_a,
        )
    ).json()
    delta_b = (
        await pg_client.post(
            "/api/v1/sync/pull",
            json={"profile_id": str(profile_b.id), "cursor": first_b["cursor"]},
            headers=headers_b,
        )
    ).json()
    for delta, card in ((delta_a, card_a), (delta_b, card_b)):
        assert len(delta["cards"]) == 1
        assert delta["cards"][0]["id"] == str(card.id)
        assert delta["cards"][0]["content"]["meanings"][0]["gloss_l1"] == "przystanek"
        assert delta["cards"][0]["gloss_primary"] == "przystanek"
        assert delta["cards"][0]["learning_generation"] == 2
        assert delta["cards"][0]["srs"]["status"] == "new"
        assert delta["cards"][0]["srs"]["repetitions"] == 0

    stale = {
        "client_id": str(uuid4()),
        "card_id": str(card_a.id),
        "grade": "good",
        "mode": "flip",
        "direction": "l2_l1",
        "correct": True,
        "reviewed_at": "2026-11-24T11:00:00Z",
        "learning_generation": 1,
    }
    pushed = (
        await pg_client.post(
            "/api/v1/sync/push", json={"reviews": [stale]}, headers=headers_a
        )
    ).json()
    assert pushed["review_results"][0]["outcome"] == "superseded"
    assert pushed["review_results"][0]["reason"] == "content_generation_superseded"
    retried = (
        await pg_client.post(
            "/api/v1/sync/push", json={"reviews": [stale]}, headers=headers_a
        )
    ).json()
    assert retried["review_results"][0]["outcome"] == "superseded"

    stale_undo = {
        "client_id": str(legacy_review.client_id),
        "previous_srs": {
            "card_id": str(card_a.id),
            "status": "review",
            "repetitions": 4,
            "learning_generation": 1,
        },
    }
    for _ in range(2):
        response = await pg_client.post("/api/v1/srs/undo", json=stale_undo, headers=headers_a)
        assert response.status_code == 200
        undo = response.json()
        assert undo["outcome"] == "superseded"
        assert undo["reason"] == "content_generation_superseded"
        assert undo["srs"]["learning_generation"] == 2
        assert undo["srs"]["status"] == "new"

    async with pg() as db:
        states = (
            await db.execute(select(SrsState).where(SrsState.card_id.in_([card_a.id, card_b.id])))
        ).scalars().all()
        history = (
            await db.execute(select(ReviewLog).where(ReviewLog.card_id == card_a.id))
        ).scalars().all()
        entry = await db.get(LexicalEntry, entry_id)
        assert {state.status for state in states} == {"new"}
        assert entry.lemma_l1_primary == "przystanek"
        assert entry.lemma_key_l1 == "przystanek"
        assert len(history) == 2


@pytest.mark.pg
async def test_publication_refuses_legacy_snapshots_until_they_are_reconciled(pg):
    from sqlalchemy import select

    from app.models import SrsState
    from app.services.shared_content import (
        content_revision,
        current_learning_generation,
        publish_lexical_content,
    )
    from app.services.word_families import _entry_for_card
    from tests.pg_factories import create_card, create_profile, create_user

    shared = {"lemma": "la parada", "meanings": [{"gloss_l1": "przystanek"}]}
    old = {"lemma": "la parada", "meanings": [{"gloss_l1": "postój"}]}
    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        entry = LexicalEntry(
            lang_pair="pl>es",
            lemma_l2="la parada",
            pos="noun",
            content=shared,
            learning_generation=2,
        )
        db.add(entry)
        await db.flush()
        card = await create_card(db, profile, "la parada", "noun", status="ready", content=old)
        card.lexical_entry = entry
        state = (
            await db.execute(select(SrsState).where(SrsState.card_id == card.id))
        ).scalar_one()
        state.status = "review"
        state.repetitions = 4
        await db.commit()
        entry_id, card_id = entry.id, card.id

    async with pg() as db:
        card = await db.get(LearningCard, card_id)
        assert card.content == old
        assert await current_learning_generation(db, card) == 1
        assert await _entry_for_card(db, card) is None
        with pytest.raises(ValueError, match="unmigrated_card_content"):
            await publish_lexical_content(
                db,
                entry_id=entry_id,
                expected_generation=2,
                expected_content_revision=content_revision(shared),
                content={"lemma": "la parada", "meanings": [{"gloss_l1": "detención"}]},
                learning_impact=True,
            )
        await db.rollback()

    async with pg() as db:
        card = await db.get(LearningCard, card_id)
        entry = await db.get(LexicalEntry, entry_id)
        state = (
            await db.execute(select(SrsState).where(SrsState.card_id == card_id))
        ).scalar_one()
        assert card.content == old
        assert entry.content == shared
        assert entry.learning_generation == 2
        assert state.status == "review"
        assert state.repetitions == 4


@pytest.mark.pg
async def test_compaction_links_only_exact_matching_content(pg):
    from app.services.shared_content import compact_exact_card_copies
    from tests.pg_factories import create_card, create_profile, create_user

    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        conflicting_user = await create_user(db)
        conflicting_profile = await create_profile(db, conflicting_user, "pl", "es")
        linked_user = await create_user(db)
        linked_profile = await create_profile(db, linked_user, "pl", "es")
        pending_user = await create_user(db)
        pending_profile = await create_profile(db, pending_user, "pl", "es")
        shared = {"lemma": "la parada", "meanings": [{"gloss_l1": "przystanek"}]}
        entry = LexicalEntry(
            lang_pair="pl>es",
            lemma_l2="la parada",
            pos="noun",
            content=shared,
        )
        cat = {"lemma": "el gato", "meanings": [{"gloss_l1": "kot"}]}
        table = {"lemma": "la mesa", "meanings": [{"gloss_l1": "stół"}]}
        advanced_entry = LexicalEntry(
            lang_pair="pl>es", lemma_l2="la mesa", pos="noun", content=table, learning_generation=2
        )
        db.add_all(
            [
                entry,
                advanced_entry,
                LexicalEntry(lang_pair="pl>es", lemma_l2="el gato", pos="noun", content=cat),
                LexicalEntry(
                    lang_pair="pl>es",
                    lemma_l2="El Gato",
                    pos="noun",
                    content={"lemma": "el gato", "meanings": [{"gloss_l1": "podnośnik"}]},
                ),
            ]
        )
        await db.flush()
        exact = await create_card(
            db, profile, "la parada", "noun", status="ready", content=shared
        )
        conflicting = await create_card(
            db,
            conflicting_profile,
            "la parada",
            "noun",
            status="ready",
            content={"lemma": "la parada", "meanings": [{"gloss_l1": "postój"}]},
        )
        linked = await create_card(
            db, linked_profile, "la parada", "noun", status="ready", content=shared
        )
        ambiguous = await create_card(
            db, profile, "el gato", "noun", status="ready", content=cat
        )
        pending = await create_card(
            db, pending_profile, "la parada", "noun", status="pending", content=shared
        )
        advanced_linked = await create_card(
            db, linked_profile, "la mesa", "noun", status="ready", content=table
        )
        advanced_unlinked = await create_card(
            db, profile, "la mesa", "noun", status="ready", content=table
        )
        linked.lexical_entry = entry
        pending.lexical_entry = entry
        advanced_linked.lexical_entry = advanced_entry
        await db.commit()
        entry_id = entry.id
        exact_id, conflicting_id, linked_id, ambiguous_id, pending_id = (
            exact.id,
            conflicting.id,
            linked.id,
            ambiguous.id,
            pending.id,
        )
        advanced_linked_id, advanced_unlinked_id = advanced_linked.id, advanced_unlinked.id

        result = await compact_exact_card_copies(db, batch_size=1)
        await db.commit()

    async with pg() as db:
        exact_after = await db.get(LearningCard, exact_id)
        conflict_after = await db.get(LearningCard, conflicting_id)
        linked_after = await db.get(LearningCard, linked_id)
        ambiguous_after = await db.get(LearningCard, ambiguous_id)
        pending_after = await db.get(LearningCard, pending_id)
        advanced_linked_after = await db.get(LearningCard, advanced_linked_id)
        advanced_unlinked_after = await db.get(LearningCard, advanced_unlinked_id)
        assert result == (1, 1)
        assert exact_after.lexical_entry_id == entry_id
        assert exact_after._content is None
        assert conflict_after.lexical_entry_id is None
        assert conflict_after.content == {"lemma": "la parada", "meanings": [{"gloss_l1": "postój"}]}
        assert linked_after._content is None
        assert ambiguous_after.lexical_entry_id is None
        assert ambiguous_after.content == cat
        assert pending_after._content == shared
        assert advanced_linked_after._content == table
        assert advanced_unlinked_after.lexical_entry_id is None
        assert advanced_unlinked_after._content == table


@pytest.mark.pg
async def test_shared_entry_cannot_be_deleted_while_it_is_the_only_content_source(pg):
    from sqlalchemy.exc import IntegrityError

    from tests.pg_factories import create_profile, create_user

    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        entry = LexicalEntry(
            lang_pair="pl>es",
            lemma_l2="la parada",
            pos="noun",
            content={"lemma": "la parada", "meanings": [{"gloss_l1": "przystanek"}]},
        )
        card = LearningCard(
            user_id=user.id,
            profile_id=profile.id,
            lexical_entry=entry,
            lemma_l2="la parada",
            pos="noun",
            content=entry.content,
            enrichment_status="ready",
        )
        db.add_all([entry, card])
        await db.commit()
        entry_id, card_id = entry.id, card.id

    async with pg() as db:
        entry = await db.get(LexicalEntry, entry_id)
        await db.delete(entry)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

    async with pg() as db:
        card = await db.get(LearningCard, card_id)
        assert card.lexical_entry_id == entry_id
        assert card.content["meanings"][0]["gloss_l1"] == "przystanek"


@pytest.mark.pg
async def test_content_source_constraint_is_added_to_existing_databases_idempotently(pg):
    from sqlalchemy import text

    from app.db.migrations import run_migrations

    async with pg() as db:
        await db.execute(
            text("ALTER TABLE learning_cards DROP CONSTRAINT ck_learning_card_content_source")
        )
        conn = await db.connection()
        await run_migrations(conn)
        await run_migrations(conn)
        exists = await db.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_constraint "
                "WHERE conrelid = 'learning_cards'::regclass "
                "AND conname = 'ck_learning_card_content_source')"
            )
        )
        assert exists
        await db.rollback()


@pytest.mark.pg
async def test_publication_rejects_stale_or_invalid_content(pg):
    from app.services.shared_content import content_revision, publish_lexical_content

    original = _complete_content("przystanek")
    first_edit = {**original, "headword_note": "poprawiona notacja"}
    async with pg() as db:
        entry = LexicalEntry(
            lang_pair="pl>es",
            lemma_l2="la parada",
            pos="noun",
            content=original,
        )
        db.add(entry)
        await db.commit()
        entry_id = entry.id

    async with pg() as db:
        await publish_lexical_content(
            db,
            entry_id=entry_id,
            expected_generation=1,
            expected_content_revision=content_revision(original),
            content=first_edit,
            learning_impact=False,
        )
        await db.commit()

    async with pg() as db:
        with pytest.raises(ValueError, match="content_revision_conflict"):
            await publish_lexical_content(
                db,
                entry_id=entry_id,
                expected_generation=1,
                expected_content_revision=content_revision(original),
                content={**original, "headword_note": "stara edycja"},
                learning_impact=False,
            )
        await db.rollback()

    invalid_contents = [
        {},
        {**original, "lemma": "otro"},
        {**original, "language": "de"},
        {**original, "meanings": [{"gloss_l1": "przystanek", "examples": []}]},
    ]
    for invalid in invalid_contents:
        async with pg() as db:
            with pytest.raises(ValueError):
                await publish_lexical_content(
                    db,
                    entry_id=entry_id,
                    expected_generation=1,
                    expected_content_revision=content_revision(first_edit),
                    content=invalid,
                    learning_impact=True,
                )
            await db.rollback()

    async with pg() as db:
        entry = await db.get(LexicalEntry, entry_id)
        assert entry.content == first_edit
        assert entry.learning_generation == 1


@pytest.mark.pg
async def test_publication_updates_headword_and_family_projections(pg):
    from sqlalchemy import select

    from app.models import WordFamily, WordFamilyMember
    from app.services.shared_content import content_revision, publish_lexical_content
    from tests.pg_factories import create_profile, create_user

    old = {
        **_complete_content("postój"),
        "lemma": "parada",
        "word_family_l2": [{"lemma": "parar", "pos": "verb", "gloss_l1": "zatrzymywać"}],
    }
    corrected = {**old, "lemma": "la parada", "meanings": _complete_content("przystanek")["meanings"]}
    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        family = WordFamily(lang_pair="pl>es")
        db.add(family)
        await db.flush()
        db.add_all(
            [
                WordFamilyMember(
                    family_id=family.id,
                    lang_pair="pl>es",
                    lemma_key="parada",
                    lemma="parada",
                    pos="noun",
                    gloss_l1="postój",
                    rank=0,
                ),
                WordFamilyMember(
                    family_id=family.id,
                    lang_pair="pl>es",
                    lemma_key="parar",
                    lemma="parar",
                    pos="verb",
                    gloss_l1="zatrzymywać",
                    rank=1,
                ),
            ]
        )
        entry = LexicalEntry(
            lang_pair="pl>es",
            lemma_l2="parada",
            lemma_l1_primary="postój",
            pos="noun",
            content=old,
            word_family_id=family.id,
        )
        related = LexicalEntry(
            lang_pair="pl>es",
            lemma_l2="parar",
            pos="verb",
            content={
                "lemma": "parar",
                "pos": "verb",
                "word_family_l2": [{"lemma": "parada", "pos": "noun", "gloss_l1": "postój"}],
            },
            word_family_id=family.id,
        )
        card = LearningCard(
            user_id=user.id,
            profile_id=profile.id,
            lexical_entry=entry,
            lemma_l2="parada",
            pos="noun",
            gloss_primary="postój",
            content=old,
            enrichment_status="ready",
        )
        db.add_all([entry, related, card])
        await db.commit()
        entry_id, related_id, card_id = entry.id, related.id, card.id

    async with pg() as db:
        await publish_lexical_content(
            db,
            entry_id=entry_id,
            expected_generation=1,
            expected_content_revision=content_revision(old),
            content=corrected,
            learning_impact=True,
        )
        await db.commit()

    async with pg() as db:
        entry = await db.get(LexicalEntry, entry_id)
        related = await db.get(LexicalEntry, related_id)
        card = await db.get(LearningCard, card_id)
        member = (
            await db.execute(
                select(WordFamilyMember).where(
                    WordFamilyMember.lang_pair == "pl>es",
                    WordFamilyMember.lemma_key == "parada",
                    WordFamilyMember.pos == "noun",
                )
            )
        ).scalar_one()
        assert entry.lemma_l2 == card.lemma_l2 == "la parada"
        assert entry.lemma_l1_primary == card.gloss_primary == "przystanek"
        assert member.article == "la"
        assert member.gloss_l1 == "przystanek"
        family_item = related.content["word_family_l2"][0]
        assert family_item["article"] == "la"
        assert family_item["gloss_l1"] == "przystanek"


@pytest.mark.pg
async def test_cosmetic_shared_update_keeps_learning_state_and_generation(pg):
    from sqlalchemy import select

    from app.models import SrsState
    from app.services.shared_content import content_revision, publish_lexical_content
    from tests.pg_factories import create_profile, create_user

    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        entry = LexicalEntry(
            lang_pair="pl>es",
            lemma_l2="la parada",
            pos="noun",
            content=_complete_content("przystanek"),
        )
        db.add(entry)
        await db.flush()
        card = LearningCard(
            user_id=user.id,
            profile_id=profile.id,
            lexical_entry=entry,
            lemma_l2="la parada",
            pos="noun",
            content=entry.content,
            enrichment_status="ready",
        )
        state = SrsState(
            card=card,
            scope="main",
            status="review",
            repetitions=5,
            interval_days=14,
        )
        db.add_all([card, state])
        await db.flush()
        entry_id, card_id = entry.id, card.id
        await publish_lexical_content(
            db,
            entry_id=entry_id,
            expected_generation=1,
            expected_content_revision=content_revision(_complete_content("przystanek")),
            content={**_complete_content("przystanek"), "headword_note": "poprawiona notacja"},
            learning_impact=False,
        )
        await db.commit()
        saved_entry = await db.get(LexicalEntry, entry_id)
        saved_state = (
            await db.execute(select(SrsState).where(SrsState.card_id == card_id))
        ).scalar_one()
        assert saved_entry.learning_generation == 1
        assert saved_state.status == "review"
        assert saved_state.repetitions == 5
        assert saved_state.interval_days == 14
