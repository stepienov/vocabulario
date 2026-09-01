"""Debug trop: lookup candidates, stitch, raw LLM JSON vs filtry."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services.llm_pricing import TokenUsage
from app.services.llm_usage import (
    bind_llm_usage_context,
    build_llm_request_json,
    clear_llm_usage_context,
    current_llm_usage_context,
    payload_cutoff,
    record_llm_usage,
)
from app.services.lookup_events import lookup_event_matches_lemma, slim_lookup_candidates
from app.services.word_family_quality import filter_word_family
from app.models import LlmCallPayload, LlmUsage


def test_slim_lookup_candidates_keeps_lemma_fields():
    cid = uuid4()
    slim = slim_lookup_candidates(
        [
            {
                "lemma": "site",
                "pos": "noun",
                "gloss": "miejsce",
                "lexical_entry_id": cid,
                "extra": "drop-me",
            },
            {"pos": "verb"},
        ]
    )
    assert slim == [
        {
            "lemma": "site",
            "pos": "noun",
            "gloss": "miejsce",
            "lexical_entry_id": str(cid),
        }
    ]


def test_lookup_event_matches_query_or_candidate():
    event = SimpleNamespace(
        query="site",
        query_norm="site",
        candidates=[{"lemma": "the site", "pos": "noun"}],
    )
    assert lookup_event_matches_lemma(event, "site", "noun")
    assert lookup_event_matches_lemma(event, "the site", "noun")
    other = SimpleNamespace(query="pull", query_norm="pull", candidates=[])
    assert not lookup_event_matches_lemma(other, "site", "noun")


def test_lookup_event_does_not_match_other_pos_candidate():
    event = SimpleNamespace(
        query="juego",
        query_norm="juego",
        candidates=[{"lemma": "play", "pos": "verb"}],
    )
    assert lookup_event_matches_lemma(event, "play", "verb")
    assert not lookup_event_matches_lemma(event, "play", "noun")


def test_filter_word_family_does_not_mutate_raw_llm_list():
    raw = [{"lemma": "irrelevante", "pos": "adj", "gloss_l1": "nieistotny"}]
    snapshot = json.dumps(raw, sort_keys=True)
    kept, antonyms = filter_word_family("relevante", "adj", raw, [], "es")
    assert json.dumps(raw, sort_keys=True) == snapshot
    assert kept == []
    assert antonyms[0]["lemma"] == "irrelevante"


def test_build_llm_request_json_prefers_dynamic_prompt():
    payload = build_llm_request_json(
        purpose="enrich_core",
        model="gpt-5.6-terra",
        schema_name="enrich_core",
        prompt="STATIC\nDYNAMIC lemma=site",
        prompt_dynamic="DYNAMIC lemma=site",
        cache_key="en",
    )
    assert payload["prompt_dynamic"] == "DYNAMIC lemma=site"
    assert "STATIC" not in (payload["prompt_dynamic"] or "")
    assert payload["purpose"] == "enrich_core"


def test_payload_cutoff_uses_ttl_days():
    now = datetime(2026, 8, 26, tzinfo=UTC)
    assert payload_cutoff(now=now, days=30) == now - timedelta(days=30)


def test_bind_lookup_event_id():
    clear_llm_usage_context()
    event_id = uuid4()
    bind_llm_usage_context(
        overwrite_operation=True,
        operation_id=uuid4(),
        operation_kind="lemma_enrich",
        lookup_event_id=event_id,
    )
    assert current_llm_usage_context().lookup_event_id == event_id
    clear_llm_usage_context()


def test_record_llm_usage_stores_payload_row():
    added: list[object] = []

    class FakeSession:
        def add(self, obj: object) -> None:
            added.append(obj)

        async def commit(self) -> None:
            return None

    session = FakeSession()

    @asynccontextmanager
    async def fake_factory():
        yield session

    async def _run() -> None:
        with patch("app.db.session.async_session_factory", fake_factory):
            uid = await record_llm_usage(
                provider="mock",
                model="gpt-5.6-terra",
                purpose="enrich_core",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
                request_json={"purpose": "enrich_core", "prompt_dynamic": "site"},
                response_json={"word_family_l2": [{"lemma": "site", "pos": "verb"}]},
            )
            assert uid is not None
            kinds = [type(obj) for obj in added]
            assert kinds == [LlmUsage, LlmCallPayload]
            payload = next(obj for obj in added if isinstance(obj, LlmCallPayload))
            assert payload.response_json["word_family_l2"][0]["lemma"] == "site"

    asyncio.run(_run())


def test_record_llm_usage_keeps_metrics_if_payload_fails():
    added: list[object] = []

    class FakeSession:
        def add(self, obj: object) -> None:
            added.append(obj)

        async def commit(self) -> None:
            if any(isinstance(obj, LlmCallPayload) for obj in added):
                raise RuntimeError("payload fk")

    session = FakeSession()

    @asynccontextmanager
    async def fake_factory():
        yield session

    async def _run() -> None:
        with patch("app.db.session.async_session_factory", fake_factory):
            uid = await record_llm_usage(
                provider="mock",
                model="gpt-5.6-terra",
                purpose="enrich_core",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
                request_json={"purpose": "enrich_core"},
                response_json={"ok": True},
            )
            assert uid is not None
            assert any(isinstance(obj, LlmUsage) for obj in added)

    asyncio.run(_run())
