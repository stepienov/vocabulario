"""enrich_study / enrich_related: model, reasoning_effort, max tokens."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.llm import LLMService


@pytest.mark.asyncio
async def test_enrich_study_and_related_use_terra_params(monkeypatch):
    svc = LLMService()
    svc.mock = False
    svc.lookup_model = "gpt-5.6-terra"
    svc.client = MagicMock()
    captured: list[dict] = []

    async def fake_create(**kwargs):
        captured.append(kwargs)
        content = (
            '{"lemma":"hablar","pos":"verb","ipa":"","headword_note":null,'
            '"meanings":[{"gloss_l1":"mówić","examples":['
            '{"l2":"a","l1":"b","cefr":"A2"},'
            '{"l2":"c","l1":"d","cefr":"B2"},'
            '{"l2":"e","l1":"f","cefr":"C2"}],'
            '"usages":[{"l2":"u","l1":"v"}]}]}'
            if captured and captured[-1].get("messages", [{}])[0].get("content", "").startswith(
                "You write the study"
            )
            else '{"synonyms_l2":[],"antonyms_l2":[],"word_family_l2":[],"associations_l2":[]}'
        )
        # Detect by system message
        system = kwargs["messages"][0]["content"]
        if "study part" in system:
            content = (
                '{"lemma":"hablar","pos":"verb","ipa":"","headword_note":null,'
                '"meanings":[{"gloss_l1":"mówić","examples":['
                '{"l2":"a","l1":"b","cefr":"A2"},'
                '{"l2":"c","l1":"d","cefr":"B2"},'
                '{"l2":"e","l1":"f","cefr":"C2"}],'
                '"usages":[{"l2":"u","l1":"v"}]}]}'
            )
        else:
            content = (
                '{"synonyms_l2":[],"antonyms_l2":[],'
                '"word_family_l2":[],"associations_l2":[]}'
            )
        msg = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=msg)
        return SimpleNamespace(choices=[choice], usage=None)

    svc.client.chat.completions.create = AsyncMock(side_effect=fake_create)
    profile = SimpleNamespace(app_lang="pl", learning_lang="es", cefr_level="A2")

    await svc.enrich_study(profile, "hablar", "verb", "mówić")
    await svc.enrich_related(profile, "hablar", "verb", "mówić")

    assert len(captured) == 2
    for kwargs in captured:
        assert kwargs["model"] == "gpt-5.6-terra"
        assert kwargs["reasoning_effort"] == "none"
        assert kwargs["max_completion_tokens"] == 2200
        assert "temperature" not in kwargs
