import json
import logging
import re
import time
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.ai.prompts.v1 import (
    IMPORT_ADAPTIVE_PROMPT_V1,
    IMPORT_ADAPTIVE_SYSTEM_V1,
    IMPORT_CLASSIFY_PROMPT_V1,
    IMPORT_CLASSIFY_SYSTEM_V1,
    IMPORT_VERIFY_LEMMAS_PROMPT_V1,
    IMPORT_VERIFY_LEMMAS_SYSTEM_V1,
    IMPORT_FORMAT_PROMPT_V1,
    IMPORT_FORMAT_SYSTEM_V1,
    IMPORT_STRUCTURE_SYSTEM_V1,
    LOOKUP_CATEGORY_DRAFT_PROMPT_V1,
    LOOKUP_CATEGORY_EXPAND_PROMPT_V1,
    LOOKUP_CATEGORY_SYSTEM_V1,
    LOOKUP_DRAFT_SYSTEM_V2,
    LOOKUP_DRAFT_USER_V2,
    LOOKUP_EXPAND_SYSTEM_V2,
    LOOKUP_EXPAND_PL_ES_EXAMPLE,
    LOOKUP_EXPAND_USER_V2,
    LOOKUP_L1_TYPO_PROMPT_V1,
    LOOKUP_PROMPT_V1,
    LOOKUP_SYSTEM_V1,
    lookup_output_form_rules_text,
    SIMILAR_WORDS_SYSTEM_V1,
    build_enrichment_core_prompt,
    build_enrichment_core_prompt_parts,
    build_examples_prompt,
    build_similar_words_fill_prompt,
    build_similar_words_prompt,
    build_similar_words_prompt_parts,
)
from app.ai.prompt_cache import (
    cached_user_message,
    pair_cache_key,
    prompt_cache_request_options,
)
from app.ai.language_typology import lang_name_en, language_pair_guidance
from app.ai.schemas.import_classify import (
    import_adaptive_enrich_schema,
    import_classify_schema,
    import_verify_lemmas_schema,
)
from app.ai.schemas.import_format import import_format_schema
from app.ai.schemas.import_structure import import_structure_schema
from app.ai.schemas.similar_words import similar_words_response_schema
from app.core.config import get_settings
from app.core.deps import lang_pair_key
from app.services.llm_pricing import parse_anthropic_usage, parse_openai_usage
from app.services.llm_usage import (
    bind_llm_usage_context,
    build_llm_request_json,
    schedule_llm_meter,
)

logger = logging.getLogger(__name__)

ENRICH_CORE_SYSTEM = (
    "You work like a bilingual dictionary. Meanings in frequency order; "
    "stylistic variants of the same sense go to synonyms, not meanings. "
    "Periphrases belong to THIS L2 only (never invent Spanish acabar de / ir a "
    "for other L2) and are NOT lemma meanings — omit them from meanings. "
    "Synonyms/antonyms must match POS of the lemma; same-root suffixal derivatives "
    "go to word_family_l2 (other POS allowed), not synonyms. Negative prefixes "
    "(irrelevante, unhappy) are antonyms, not word family. Look-alikes with "
    "another root are not word family. "
    "associations_l2 is a 15-20 word everyday scene (mixed POS: objects, "
    "actions, qualities, people) — not synonyms, not antonyms, not same-root "
    "family. "
    "Each meaning needs exactly 3 example sentences (A2, B2, C2). "
    "No conjugation, no similar_words. JSON only."
)


def _log_import_llm(title: str, body: str) -> None:
    """Widoczne w terminalu uvicorn — pełny prompt / response importu."""
    sep = "=" * 72
    block = f"\n{sep}\n{title}\n{sep}\n{body}\n{sep}\n"
    logger.info(block)
    try:
        print(block, flush=True)
    except UnicodeEncodeError:
        # Windows cp1250 consoles can't print arrows / some Spanish diacritics
        print(block.encode("utf-8", errors="replace").decode("ascii", errors="replace"), flush=True)


class LLMService:
    def __init__(self) -> None:
        settings = get_settings()
        self.mock = settings.llm_mock or not settings.openai_api_key
        self.client = (
            AsyncOpenAI(api_key=settings.openai_api_key, timeout=90.0) if not self.mock else None
        )
        self.lookup_model = settings.llm_lookup_model
        self.enrichment_model = settings.llm_enrichment_model
        self.light_model = settings.llm_light_model
        self.import_layout_model = (
            settings.llm_import_layout_model.strip()
            or settings.llm_lookup_model
        )
        self.import_provider = (settings.llm_import_provider or "openai").strip().lower()
        self.anthropic_api_key = settings.anthropic_api_key.strip()
        self._anthropic = None
        if self.import_provider == "anthropic" and self.anthropic_api_key:
            try:
                from anthropic import AsyncAnthropic

                self._anthropic = AsyncAnthropic(api_key=self.anthropic_api_key)
            except Exception:
                logger.exception("Anthropic client init failed; falling back to OpenAI")
                self.import_provider = "openai"

    @staticmethod
    def _is_reasoning_model(model: str) -> bool:
        """Rodzina GPT-5 / o-series: brak temperature, limit jako max_completion_tokens."""
        name = model.lower()
        return name.startswith(("gpt-5", "o1", "o3", "o4"))

    async def _chat_json(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        *,
        json_schema: dict | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.2,
        provider: str | None = None,
        cache_key: str | None = None,
        prompt_static: str | None = None,
        prompt_dynamic: str | None = None,
        purpose: str = "chat_json",
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        if self.mock:
            mock_prompt = prompt
            if prompt_static is not None and prompt_dynamic is not None:
                mock_prompt = prompt_static + "\n" + prompt_dynamic
            data = self._mock_response(mock_prompt)
            schema_name = (json_schema or {}).get("name") or "chat_json"
            schedule_llm_meter(
                {
                    "provider": "mock",
                    "model": model,
                    "purpose": purpose,
                    "status": "ok",
                    "request_json": build_llm_request_json(
                        purpose=purpose,
                        model=model,
                        schema_name=schema_name,
                        prompt=prompt,
                        prompt_dynamic=prompt_dynamic,
                        cache_key=cache_key,
                        reasoning_effort=reasoning_effort,
                    ),
                    "response_json": data if isinstance(data, dict) else None,
                }
            )
            return data
        use_provider = (provider or "openai").strip().lower()
        schema_name = (json_schema or {}).get("name") or "chat_json"
        prompt_len = len(prompt)
        if prompt_static is not None and prompt_dynamic is not None:
            prompt_len = len(prompt_static) + len(prompt_dynamic)
        started = time.perf_counter()
        usage = None
        try:
            if use_provider == "anthropic" and self._anthropic is not None:
                data, usage = await self._chat_json_anthropic(
                    model,
                    prompt_static + "\n" + prompt_dynamic
                    if prompt_static and prompt_dynamic
                    else prompt,
                    system,
                    json_schema=json_schema,
                    max_tokens=max_tokens,
                )
            else:
                data, usage = await self._chat_json_openai(
                    model,
                    prompt,
                    system,
                    json_schema=json_schema,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    cache_key=cache_key,
                    prompt_static=prompt_static,
                    prompt_dynamic=prompt_dynamic,
                    reasoning_effort=reasoning_effort,
                )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            schedule_llm_meter(
                {
                    "provider": use_provider,
                    "model": model,
                    "purpose": purpose,
                    "status": "error",
                    "duration_ms": duration_ms,
                    "usage": usage,
                    "request_json": build_llm_request_json(
                        purpose=purpose,
                        model=model,
                        schema_name=schema_name,
                        prompt=prompt,
                        prompt_dynamic=prompt_dynamic,
                        cache_key=cache_key,
                        reasoning_effort=reasoning_effort,
                    ),
                },
                {
                    "level": "error",
                    "category": "llm",
                    "event": "llm_call",
                    "status": "error",
                    "duration_ms": duration_ms,
                    "message": f"{use_provider}:{model} {schema_name} failed",
                    "payload": {
                        "provider": use_provider,
                        "model": model,
                        "schema": schema_name,
                        "prompt_chars": prompt_len,
                        "cache_key": cache_key,
                        "purpose": purpose,
                    },
                    "exc": exc,
                },
            )
            raise

        duration_ms = int((time.perf_counter() - started) * 1000)
        schedule_llm_meter(
            {
                "provider": use_provider,
                "model": model,
                "purpose": purpose,
                "status": "ok",
                "duration_ms": duration_ms,
                "usage": usage,
                "request_json": build_llm_request_json(
                    purpose=purpose,
                    model=model,
                    schema_name=schema_name,
                    prompt=prompt,
                    prompt_dynamic=prompt_dynamic,
                    cache_key=cache_key,
                    reasoning_effort=reasoning_effort,
                ),
                "response_json": data if isinstance(data, dict) else None,
            },
            {
                "level": "info",
                "category": "llm",
                "event": "llm_call",
                "status": "ok",
                "duration_ms": duration_ms,
                "message": f"{use_provider}:{model} {schema_name}",
                "payload": {
                    "provider": use_provider,
                    "model": model,
                    "schema": schema_name,
                    "prompt_chars": prompt_len,
                    "cache_key": cache_key,
                    "purpose": purpose,
                },
            },
        )
        return data

    async def _chat_json_openai(
        self,
        model: str,
        prompt: str,
        system: str | None,
        *,
        json_schema: dict | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.2,
        cache_key: str | None = None,
        prompt_static: str | None = None,
        prompt_dynamic: str | None = None,
        reasoning_effort: str | None = None,
    ) -> tuple[dict[str, Any], Any]:
        assert self.client is not None
        system_content = system or (
            "Jesteś asystentem językowym. Zwracasz wyłącznie poprawny JSON "
            "bez markdown i bez komentarzy."
        )
        use_cache = (
            cache_key
            and prompt_static is not None
            and prompt_dynamic is not None
            and self._is_reasoning_model(model)
            and len(prompt_static) >= 4096  # ~1024 tokens — OpenAI cache minimum
        )
        if use_cache:
            user_content: str | list[dict[str, Any]] = cached_user_message(
                static=prompt_static,
                dynamic=prompt_dynamic,
            )
        elif prompt_static is not None and prompt_dynamic is not None:
            user_content = prompt_static + "\n" + prompt_dynamic
        else:
            user_content = prompt

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
        }
        if use_cache and cache_key:
            kwargs.update(prompt_cache_request_options(cache_key=cache_key))
        if not self._is_reasoning_model(model):
            kwargs["temperature"] = temperature
        if json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": json_schema["name"],
                    "strict": True,
                    "schema": json_schema["schema"],
                },
            }
        else:
            kwargs["response_format"] = {"type": "json_object"}
        if max_tokens is not None:
            limit_key = (
                "max_completion_tokens"
                if self._is_reasoning_model(model)
                else "max_tokens"
            )
            kwargs[limit_key] = max_tokens
        if self._is_reasoning_model(model) and reasoning_effort is not None:
            kwargs["reasoning_effort"] = reasoning_effort
        response = await self.client.chat.completions.create(**kwargs)
        usage = parse_openai_usage(response)
        content = response.choices[0].message.content or "{}"
        return json.loads(content), usage

    async def _chat_json_anthropic(
        self,
        model: str,
        prompt: str,
        system: str | None,
        *,
        json_schema: dict | None = None,
        max_tokens: int | None = None,
    ) -> tuple[dict[str, Any], Any]:
        """Anthropic path: force JSON via instruction + parse (no native json_schema)."""
        assert self._anthropic is not None
        schema_hint = ""
        if json_schema:
            schema_hint = (
                "\n\nZwróć JSON zgodny ze schematem "
                f"{json_schema.get('name', 'response')}."
            )
        system_content = (system or "Return only valid JSON.") + schema_hint
        msg = await self._anthropic.messages.create(
            model=model,
            max_tokens=max_tokens or 4096,
            system=system_content,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", "") == "text"
        )
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return json.loads(text or "{}"), parse_anthropic_usage(msg)

    def _mock_similar_words(self, lemma: str, pos: str = "verb") -> list[dict[str, str]]:
        """Dystraktory — inne hasła, nie odmiany lematu."""
        pos_val = (pos or "verb").strip().lower() or "verb"
        pools: dict[str, list[tuple[str, str, str]]] = {
            "apoyar": [
                ("apagar", "verb", "gasić"),
                ("apegar", "verb", "przyklejać"),
                ("apilar", "verb", "układać w stos"),
                ("aplicar", "verb", "stosować"),
                ("aprobar", "verb", "zatwierdzać"),
                ("aportar", "verb", "wnosić"),
                ("apostar", "verb", "stawiać"),
                ("apuntar", "verb", "wskazywać"),
                ("aplacar", "verb", "uspokajać"),
                ("aplanar", "verb", "wyrównywać"),
                ("aparar", "verb", "parować"),
                ("apretar", "verb", "ściskać"),
            ],
            "tender": [
                ("entender", "verb", "rozumieć"),
                ("defender", "verb", "bronić"),
                ("vender", "verb", "sprzedawać"),
                ("contender", "verb", "walczyć"),
                ("pretender", "verb", "udawać"),
                ("extender", "verb", "rozszerzać"),
                ("atender", "verb", "obsługiwać"),
                ("entretener", "verb", "rozweselać"),
                ("ascender", "verb", "wznosić się"),
                ("descender", "verb", "schodzić"),
                ("suspender", "verb", "zawieszać"),
                ("transcender", "verb", "przekraczać"),
            ],
        }
        if lemma.lower() in pools:
            return [
                {"lemma": l, "pos": p, "gloss_l1": g}
                for l, p, g in pools[lemma.lower()]
            ]
        if pos_val in {"phrase", "construction", "sentence", "other"}:
            token = lemma.split()[0] if lemma.strip() else "x"
            return [
                {
                    "lemma": f"{token} mock {i}",
                    "pos": pos_val,
                    "gloss_l1": f"gloss {i}",
                }
                for i in range(12)
            ]
        base = lemma[:4] if len(lemma) >= 4 else lemma
        variants = [
            (f"ab{base[-2:]}", pos_val, "gasić"),
            (f"ac{base[-2:]}", pos_val, "przyklejać"),
            (f"ad{base[-2:]}", pos_val, "układać"),
            (f"al{base[-2:]}", pos_val, "stosować"),
            (f"am{base[-2:]}", pos_val, "stawiać"),
            (f"an{base[-2:]}", pos_val, "wskazywać"),
            (f"as{base[-2:]}", pos_val, "wnosić"),
            (f"at{base[-2:]}", pos_val, "zatwierdzać"),
            (f"av{base[-2:]}", pos_val, "parować"),
            (f"az{base[-2:]}", pos_val, "ściskać"),
            (f"ag{base[-2:]}", pos_val, "oddawać"),
            (f"aj{base[-2:]}", pos_val, "odwoływać"),
        ]
        return [{"lemma": l, "pos": p, "gloss_l1": g} for l, p, g in variants]

    def _mock_response(self, prompt: str) -> dict[str, Any]:
        if "full card audit" in prompt.lower() or "flashcard correction" in prompt.lower():
            note_match = re.search(r"User note \(pay extra attention\):\s*(.+)", prompt, re.I)
            if not note_match:
                note_match = re.search(r"User note:\s*(.+)", prompt, re.I)
            note = (note_match.group(1).strip().split("\n")[0] if note_match else "").lower()
            if "accept" in note:
                gloss_match = re.search(r'"gloss_primary":\s*"([^"]+)"', prompt)
                gloss = gloss_match.group(1) if gloss_match else "poprawione znaczenie"
                return {
                    "status": "accepted",
                    "code": "correction_accepted",
                    "reason": "Mock: correction accepted for testing.",
                    "patch": {"gloss_primary": gloss},
                }
            if '"—"' in prompt or '": "—"' in prompt:
                return {
                    "status": "accepted",
                    "code": "correction_accepted",
                    "reason": "Mock: fixed placeholder conjugation.",
                    "patch": {
                        "conjugation": {
                            "presente": {
                                "yo": "como",
                                "tú": "comes",
                                "él/ella/usted": "come",
                                "nosotros": "comemos",
                                "vosotros": "coméis",
                                "ellos/ellas/ustedes": "comen",
                            }
                        }
                    },
                }
            if '"lemma": "hablar"' in prompt and "to eat" in prompt:
                return {
                    "status": "accepted",
                    "code": "correction_accepted",
                    "reason": "Mock: fixed gloss.",
                    "patch": {"gloss_primary": "to speak"},
                }
            if '"lemma": "escribir"' in prompt and "to run" in prompt:
                return {
                    "status": "accepted",
                    "code": "correction_accepted",
                    "reason": "Mock: fixed gloss.",
                    "patch": {"gloss_primary": "to write"},
                }
            if '"lemma": "vivir"' in prompt and '"pos": "noun"' in prompt:
                return {
                    "status": "accepted",
                    "code": "correction_accepted",
                    "reason": "Mock: fixed POS.",
                    "patch": {"pos": "verb"},
                }
            return {
                "status": "rejected",
                "code": "correction_unfounded",
                "reason": "Mock: no factual errors found on full card audit.",
            }
        if "Żadne nie może być na tej liście:" in prompt:
            count_match = re.search(r"Podaj (\d+) (?:słów|pozycji)", prompt)
            count = int(count_match.group(1)) if count_match else 12
            exclude_match = re.search(r"Żadne nie może być na tej liście: (.+)", prompt)
            excluded = set()
            if exclude_match:
                excluded = {
                    word.strip().lower()
                    for word in exclude_match.group(1).split(",")
                    if word.strip() and word.strip() != "(brak)"
                }
            pos_match = re.search(r"Część mowy:\s*(\S+)", prompt)
            pos = (pos_match.group(1) if pos_match else "verb").strip()
            pool = self._mock_similar_words("palabra", pos)
            filtered = [i for i in pool if i["lemma"].lower() not in excluded]
            return {"similar_words": filtered[:count]}
        if "Hasło na fiszce:" in prompt or "Słowo na fiszce:" in prompt:
            match = re.search(r"(?:Hasło|Słowo) na fiszce:\s*(.+)", prompt)
            lemma = match.group(1).strip().rstrip(".”„") if match else "palabra"
            pos_match = re.search(r"^POS:\s*(\S+)", prompt, re.M)
            pos = (pos_match.group(1) if pos_match else "verb").strip()
            return {"similar_words": self._mock_similar_words(lemma, pos)}
        if "candidates" in prompt or "kandydat" in prompt.lower() or "Candidate list" in prompt:
            q = re.search(r'User query string:\s*"([^"]+)"', prompt)
            if not q:
                q = re.search(r'Wpisane zapytanie:\s*"([^"]+)"', prompt)
            if not q:
                q = re.search(r'Typed string:\s*"([^"]+)"', prompt)
            if not q:
                q = re.search(r"(?:Query|Text|User input|Word)\s*:\s*(.+)", prompt, re.I)
            lemma = (q.group(1).strip().split()[0] if q else None) or "casa"
            lemma = lemma.strip(".,;\"'")
            return {
                "candidates": [
                    {"lemma": lemma, "pos": "noun", "gloss": f"mock gloss for {lemma}"},
                    {"lemma": f"{lemma}2", "pos": "verb", "gloss": f"mock gloss 2 for {lemma}"},
                ]
            }
        match = re.search(r"Lemat \(L2\):\s*(\S+)", prompt)
        lemma = match.group(1) if match else "palabra"
        return {
            "schema_version": "vocabulario.card.v1",
            "lemma": lemma,
            "language": "es",
            "pos": "verb",
            "ipa": "",
            "meanings": [
                {
                    "gloss_l1": "przykładowe znaczenie",
                    "synonyms_l1": ["synonim"],
                    "examples": [
                        {"l2": f"Ejemplo A2 con {lemma}.", "l1": "Przykład A2.", "cefr": "A2"},
                        {"l2": f"Ejemplo B2 con {lemma}.", "l1": "Przykład B2.", "cefr": "B2"},
                        {"l2": f"Ejemplo C2 con {lemma}.", "l1": "Przykład C2.", "cefr": "C2"},
                    ],
                    "usages": [],
                }
            ],
            "synonyms_l2": [],
            "antonyms_l2": [],
            "word_family_l2": [],
            "associations_l2": [
                {
                    "lemma": "escena",
                    "pos": "noun",
                    "article": "la",
                    "gloss_l1": "scena",
                }
            ],
            "similar_words": self._mock_similar_words(lemma),
            "inflection": None,
            "conjugation": None,
            "notes": None,
            "confidence": 0.95,
        }

    async def lookup(
        self, text: str, native: str, learning: str, cefr: str
    ) -> list[dict[str, Any]]:
        prompt = LOOKUP_PROMPT_V1.format(
            native_name=lang_name_en(native),
            learning_name=lang_name_en(learning),
            text=text,
            cefr=cefr,
            pair_guidance=language_pair_guidance(native=native, learning=learning),
            lookup_output_form_rules=lookup_output_form_rules_text(native, learning),
        )
        bind_llm_usage_context(query=text, lang_pair=lang_pair_key(native, learning))
        data = await self._chat_json(
            self.lookup_model,
            prompt,
            system=LOOKUP_SYSTEM_V1,
            purpose="lookup",
        )
        return data.get("candidates", [])

    @staticmethod
    def _already_block(already: list[dict[str, Any]]) -> str:
        rows = [
            c
            for c in already
            if isinstance(c, dict) and (c.get("lemma") or "").strip()
        ]
        if not rows:
            return (
                "None yet — this is a cold start. Return the full high-recall "
                "union of all plausible readings (up to 16)."
            )
        lines = ["Already stored (do NOT repeat these lemma+pos pairs):"]
        for c in rows:
            lines.append(
                f"- lemma={c.get('lemma')}; pos={c.get('pos')}; gloss={c.get('gloss')}"
            )
        return "\n".join(lines)

    @staticmethod
    def _expand_already_block(already: list[dict[str, Any]]) -> str:
        rows = [
            c
            for c in already
            if isinstance(c, dict) and (c.get("lemma") or "").strip()
        ]
        if not rows:
            return "Nothing shown yet."
        lines = ["Already shown, do not repeat these lemma+pos pairs:"]
        for c in rows:
            lines.append(
                f"- lemma={c.get('lemma')}; pos={c.get('pos')}; gloss={c.get('gloss')}"
            )
        return "\n".join(lines)

    async def lookup_expand(
        self,
        text: str,
        native: str,
        learning: str,
        already: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """One-shot lookup: full union on cold start, only new rows when cache exists."""
        prompt = LOOKUP_EXPAND_USER_V2.format(
            native_name=lang_name_en(native),
            learning_name=lang_name_en(learning),
            text=text,
            already_block=self._expand_already_block(already or []),
        )
        if (native or "").lower().startswith("pl") and (learning or "").lower().startswith("es"):
            prompt += "\n" + LOOKUP_EXPAND_PL_ES_EXAMPLE
        bind_llm_usage_context(query=text, lang_pair=lang_pair_key(native, learning))
        data = await self._chat_json(
            self.lookup_model,
            prompt,
            system=LOOKUP_EXPAND_SYSTEM_V2,
            max_tokens=500,
            reasoning_effort="none",
            purpose="lookup_expand",
        )
        return data.get("candidates", [])

    async def lookup_draft(
        self,
        text: str,
        native: str,
        learning: str,
    ) -> list[dict[str, Any]]:
        """Cheap first-paint lookup on the light model."""
        prompt = LOOKUP_DRAFT_USER_V2.format(
            native_name=lang_name_en(native),
            learning_name=lang_name_en(learning),
            text=text,
        )
        bind_llm_usage_context(query=text, lang_pair=lang_pair_key(native, learning))
        data = await self._chat_json(
            self.lookup_model,
            prompt,
            system=LOOKUP_DRAFT_SYSTEM_V2,
            max_tokens=400,
            reasoning_effort="none",
            purpose="lookup_draft",
        )
        return data.get("candidates", [])

    async def lookup_category_draft(
        self,
        text: str,
        native: str,
        learning: str,
        cefr: str,
    ) -> list[dict[str, Any]]:
        prompt = LOOKUP_CATEGORY_DRAFT_PROMPT_V1.format(
            native_name=lang_name_en(native),
            learning_name=lang_name_en(learning),
            text=text,
            pair_guidance=language_pair_guidance(native=native, learning=learning),
        )
        bind_llm_usage_context(query=text, lang_pair=lang_pair_key(native, learning))
        data = await self._chat_json(
            self.light_model,
            prompt,
            system=LOOKUP_CATEGORY_SYSTEM_V1,
            max_tokens=1200,
            purpose="lookup_category_draft",
        )
        return data.get("candidates", [])

    async def lookup_category_expand(
        self,
        text: str,
        native: str,
        learning: str,
        cefr: str,
        already: list[dict[str, Any]] | None = None,
        theme: str = "",
    ) -> list[dict[str, Any]]:
        prompt = LOOKUP_CATEGORY_EXPAND_PROMPT_V1.format(
            native_name=lang_name_en(native),
            learning_name=lang_name_en(learning),
            text=text,
            theme=(theme or "").strip() or "same theme as the seed",
            pair_guidance=language_pair_guidance(native=native, learning=learning),
            lookup_output_form_rules=lookup_output_form_rules_text(native, learning),
            already_block=self._already_block(already or []),
        )
        bind_llm_usage_context(query=text, lang_pair=lang_pair_key(native, learning))
        data = await self._chat_json(
            self.lookup_model,
            prompt,
            system=LOOKUP_CATEGORY_SYSTEM_V1,
            purpose="lookup_category_expand",
        )
        return data.get("candidates", [])

    async def lookup_l1_typo(
        self, text: str, native: str, learning: str, cefr: str
    ) -> list[dict[str, Any]]:
        """Second-pass lookup: force interpretation as native-language typo."""
        prompt = LOOKUP_L1_TYPO_PROMPT_V1.format(
            native_name=lang_name_en(native),
            learning_name=lang_name_en(learning),
            text=text,
            pair_guidance=language_pair_guidance(native=native, learning=learning),
            lookup_output_form_rules=lookup_output_form_rules_text(native, learning),
        )
        data = await self._chat_json(
            self.lookup_model,
            prompt,
            system=(
                "Correct an L1 typo and return L2 dictionary headwords as JSON. "
                "Interpret the query generously (typos, diacritics, inflection). "
                "Output always dictionary citation forms: lemma = L2 headword, "
                "gloss = L1 headword (singular noun / infinitive verb). "
                "If the typed string is also a valid L2 headword, include that reading too."
            ),
            purpose="lookup_l1_typo",
        )
        return data.get("candidates", [])

    async def enrich_core(
        self,
        lemma: str,
        pos: str | None,
        native: str,
        learning: str,
        cefr: str,
        *,
        gloss_hint: str | None = None,
        retry: bool = False,
    ) -> dict[str, Any]:
        pos_val = pos or "unknown"
        static, dynamic = build_enrichment_core_prompt_parts(
            native=native,
            learning=learning,
            lemma=lemma,
            pos=pos_val,
            cefr=cefr,
            gloss_hint=gloss_hint,
            retry=retry,
        )
        prompt = static + "\n" + dynamic
        cache_key = pair_cache_key("enrich", native, learning, extra=cefr)
        bind_llm_usage_context(
            lemma=lemma,
            pos=pos_val,
            lang_pair=lang_pair_key(native, learning),
        )
        return await self._chat_json(
            self.lookup_model,
            prompt,
            system=ENRICH_CORE_SYSTEM,
            cache_key=cache_key,
            prompt_static=static,
            prompt_dynamic=dynamic,
            purpose="enrich_core",
        )

    async def repair_related_articles(
        self,
        items: list[dict],
        learning_lang: str | None,
    ) -> dict[str, Any]:
        """Return {articles: {lemma: article}} for nouns still missing a citation article."""
        if self.mock or not items:
            return {"articles": {}}
        lines = "\n".join(
            f"- lemma={item.get('lemma')!r} pos={item.get('pos')!r}"
            for item in items
        )
        prompt = (
            f"Language: {learning_lang}\n"
            "For each noun, give the dictionary citation article only "
            "(es: el/la/los/las; fr: le/la/les/l'; de: der/die/das; "
            "it: il/lo/la/l'/i/gli/le; pt: o/a/os/as; ar: ال). "
            "Copy the real article — do not invent from gender charts. "
            "If unsure, omit that lemma.\n"
            f"{lines}\n"
            'JSON: {"articles": {"lemma": "article"}}'
        )
        return await self._chat_json(
            self.light_model,
            prompt,
            system="Return only JSON with an articles object. Never invent articles.",
            purpose="article_repair",
        )

    async def generate_examples(
        self,
        lemma: str,
        pos: str | None,
        glosses: list[str],
        native: str,
        learning: str,
        retry: bool = False,
    ) -> dict[str, Any]:
        prompt = build_examples_prompt(
            native=native,
            learning=learning,
            lemma=lemma,
            pos=pos or "unknown",
            glosses=glosses,
            retry=retry,
        )
        bind_llm_usage_context(
            lemma=lemma,
            pos=pos or "unknown",
            lang_pair=lang_pair_key(native, learning),
        )
        return await self._chat_json(
            self.light_model,
            prompt,
            system=(
                "Generujesz przykłady zdań. Dla każdego znaczenia MUSISZ zwrócić dokładnie "
                "3 zdania: jedno A2, jedno B2, jedno C2. Poziomy muszą się wyraźnie "
                "różnić trudnością. ZAKAZ powtarzania tego samego zdania l2 między "
                "znaczeniami. Tylko poprawny JSON."
            ),
            purpose="examples",
        )

    async def generate_lsp_inflection(
        self,
        prompt: str,
        *,
        cache_key: str | None = None,
        prompt_static: str | None = None,
        prompt_dynamic: str | None = None,
    ) -> dict[str, Any]:
        """Jeden krok inflection wg manifestu LSP."""
        if self.mock:
            return {
                "verbs": {
                    "tenses": {"czas_przeszly": {"ja_m": "mock"}},
                    "non_finite": {},
                    "ui_meta": {"inflection_kind": "person_tense"},
                },
                "periphrases": [],
            }
        data = await self._chat_json(
            self.enrichment_model,
            prompt,
            system=(
                "You are a rigorous morphologist. Return only attested inflected forms. "
                "Never use placeholder dashes — omit inapplicable categories instead. JSON only."
            ),
            cache_key=cache_key,
            prompt_static=prompt_static,
            prompt_dynamic=prompt_dynamic,
            purpose="inflection",
        )
        if isinstance(data.get("inflection"), dict):
            return data["inflection"]
        return data if isinstance(data, dict) else {}

    async def enrich(
        self,
        lemma: str,
        pos: str | None,
        native: str,
        learning: str,
        cefr: str,
    ) -> dict[str, Any]:
        """@deprecated Użyj enrich_card_content() — zachowane dla mocków."""
        prompt = build_enrichment_core_prompt(
            native=native,
            learning=learning,
            lemma=lemma,
            pos=pos or "unknown",
            cefr=cefr,
        )
        return await self._chat_json(self.enrichment_model, prompt,
            purpose="enrich",
        )

    def _parse_similar_words(self, data: dict[str, Any]) -> list[dict]:
        raw = data.get("similar_words", [])
        result: list[dict] = []
        for item in raw:
            if not isinstance(item, dict) or not item.get("lemma"):
                continue
            entry: dict = {
                "lemma": item["lemma"],
                "gloss_l1": item.get("gloss_l1") or item.get("gloss") or "?",
            }
            if item.get("pos"):
                entry["pos"] = item["pos"]
            result.append(entry)
        return result

    async def generate_similar_words(
        self,
        lemma: str,
        pos: str | None,
        native: str,
        learning: str,
        *,
        count: int,
    ) -> list[dict]:
        """Dystraktory do fiszki: najpierw podobne formalnie, resztę z poziomu B2."""
        pos_val = pos or "unknown"
        static, dynamic = build_similar_words_prompt_parts(
            native=native,
            learning=learning,
            lemma=lemma,
            pos=pos_val,
            count=count,
        )
        prompt = static + "\n" + dynamic
        cache_key = pair_cache_key("similar", native, learning, extra=pos_val)
        bind_llm_usage_context(
            lemma=lemma,
            pos=pos_val,
            lang_pair=lang_pair_key(native, learning),
        )
        data = await self._chat_json(
            self.light_model,
            prompt,
            system=SIMILAR_WORDS_SYSTEM_V1,
            json_schema=similar_words_response_schema(count=count),
            max_tokens=4000,
            cache_key=cache_key,
            prompt_static=static,
            prompt_dynamic=dynamic,
            purpose="similar_words",
        )
        return self._parse_similar_words(data)

    async def generate_filler_words(
        self,
        pos: str | None,
        native: str,
        learning: str,
        *,
        exclude: list[str],
        count: int,
    ) -> list[dict]:
        """Pula słów z poziomu B2 — awaryjne dopełnienie brakujących pozycji."""
        if count <= 0:
            return []
        pos_val = pos or "unknown"
        prompt = build_similar_words_fill_prompt(
            native=native,
            learning=learning,
            pos=pos_val,
            exclude=exclude,
            count=count,
        )
        data = await self._chat_json(
            self.light_model,
            prompt,
            system=SIMILAR_WORDS_SYSTEM_V1,
            json_schema=similar_words_response_schema(count=count),
            max_tokens=4000,
            purpose="filler",
        )
        return self._parse_similar_words(data)

    async def analyze_import_format(
        self,
        *,
        native: str,
        learning: str,
        kind_hint: str,
        field_names: list[str] | None,
        raw_sample: str,
    ) -> dict:
        """Surowy tekst → instrukcja segmentacji na notatki/pola."""
        prompt = IMPORT_FORMAT_PROMPT_V1.format(
            native_name=lang_name_en(native),
            learning_name=lang_name_en(learning),
            kind_hint=kind_hint,
            field_names=json.dumps(field_names, ensure_ascii=False)
            if field_names
            else "nieznane",
            raw_sample=raw_sample,
        )
        _log_import_llm(
            f"IMPORT FORMAT → PROMPT (model={self.lookup_model}, kind={kind_hint})",
            f"--- SYSTEM ---\n{IMPORT_FORMAT_SYSTEM_V1}\n\n--- USER ---\n{prompt}",
        )
        result = await self._chat_json(
            self.lookup_model,
            prompt,
            system=IMPORT_FORMAT_SYSTEM_V1,
            json_schema=import_format_schema(),
            max_tokens=3500,
            temperature=0.1,
            purpose="import_format",
        )
        _log_import_llm(
            "IMPORT FORMAT ← RESPONSE",
            json.dumps(result, ensure_ascii=False, indent=2),
        )
        return result

    async def analyze_import_classify(
        self,
        *,
        native: str,
        learning: str,
        notes: list[list[str]],
    ) -> dict:
        compact = []
        for note in notes:
            row = []
            for cell in note:
                row.append(cell[:300] if len(cell) > 300 else cell)
            compact.append(row)
        prompt = IMPORT_CLASSIFY_PROMPT_V1.format(
            native_name=lang_name_en(native),
            learning_name=lang_name_en(learning),
            notes_json=json.dumps(compact, ensure_ascii=False, indent=2),
        )
        _log_import_llm(
            f"IMPORT CLASSIFY → PROMPT (model={self.lookup_model}, n={len(notes)})",
            f"--- SYSTEM ---\n{IMPORT_CLASSIFY_SYSTEM_V1}\n\n--- USER ---\n{prompt}",
        )
        result = await self._chat_json(
            self.lookup_model,
            prompt,
            system=IMPORT_CLASSIFY_SYSTEM_V1,
            json_schema=import_classify_schema(),
            max_tokens=6000,
            temperature=0.1,
            purpose="import_classify",
        )
        _log_import_llm(
            "IMPORT CLASSIFY ← RESPONSE",
            json.dumps(result, ensure_ascii=False, indent=2),
        )
        return result

    async def analyze_import_verify_lemmas(
        self,
        *,
        learning: str,
        lemmas: list[str],
    ) -> dict:
        prompt = IMPORT_VERIFY_LEMMAS_PROMPT_V1.format(
            learning_name=lang_name_en(learning),
            lemmas_json=json.dumps(
                [{"index": i, "lemma": lemma} for i, lemma in enumerate(lemmas)],
                ensure_ascii=False,
                indent=2,
            ),
        )
        _log_import_llm(
            f"IMPORT VERIFY LEMMAS → PROMPT (model={self.lookup_model}, n={len(lemmas)})",
            f"--- SYSTEM ---\n{IMPORT_VERIFY_LEMMAS_SYSTEM_V1}\n\n--- USER ---\n{prompt}",
        )
        result = await self._chat_json(
            self.lookup_model,
            prompt,
            system=IMPORT_VERIFY_LEMMAS_SYSTEM_V1,
            json_schema=import_verify_lemmas_schema(),
            max_tokens=2000,
            temperature=0,
            purpose="import_verify",
        )
        _log_import_llm(
            "IMPORT VERIFY LEMMAS ← RESPONSE",
            json.dumps(result, ensure_ascii=False, indent=2),
        )
        return result

    async def enrich_adaptive_entry(
        self,
        *,
        native: str,
        learning: str,
        cefr: str,
        entry_kind: str,
        headword: str,
        gloss: str | None,
        base_lemma: str | None,
        pattern: str | None,
    ) -> dict:
        prompt = IMPORT_ADAPTIVE_PROMPT_V1.format(
            native_name=lang_name_en(native),
            learning_name=lang_name_en(learning),
            cefr=cefr,
            entry_kind=entry_kind,
            headword=headword,
            gloss=gloss or "",
            base_lemma=base_lemma or "",
            pattern=pattern or "",
        )
        bind_llm_usage_context(
            lemma=headword,
            lang_pair=lang_pair_key(native, learning),
        )
        return await self._chat_json(
            self.lookup_model,
            prompt,
            system=IMPORT_ADAPTIVE_SYSTEM_V1,
            json_schema=import_adaptive_enrich_schema(),
            max_tokens=3500,
            temperature=0.2,
            purpose="adaptive",
        )

    async def analyze_import_structure(
        self,
        *,
        native: str,
        learning: str,
        kind: str,
        field_names: list[str] | None,
        sample_notes: list[list[str]],
        total_notes: int,
    ) -> dict:
        """Ustal jak wyciągnąć hasła L2 z dowolnej talii Anki/CSV."""
        from app.services.import_ai import build_import_structure_prompt

        prompt = build_import_structure_prompt(
            native=native,
            learning=learning,
            kind=kind,
            field_names=field_names,
            sample_notes=sample_notes,
            total_notes=total_notes,
        )
        _log_import_llm(
            f"IMPORT LLM → PROMPT (model={self.lookup_model}, mock={self.mock}, "
            f"kind={kind}, notes={total_notes})",
            f"--- SYSTEM ---\n{IMPORT_STRUCTURE_SYSTEM_V1}\n\n--- USER ---\n{prompt}",
        )
        if self.mock:
            # mock: prefer Spanish / index 1
            idx = 0
            if field_names:
                for i, name in enumerate(field_names):
                    if "spanish" in name.lower() or "lemma" in name.lower():
                        idx = i
                        break
                else:
                    idx = 1 if len(field_names) > 1 else 0
            else:
                idx = 1
            result = {
                "strategy": "field_index" if (field_names and len(field_names) > 1) or (
                    sample_notes and sample_notes[0] and len(sample_notes[0]) > 1
                ) else "plain_list",
                "field_index": idx if (field_names and len(field_names) > 1) or (
                    sample_notes and sample_notes[0] and len(sample_notes[0]) > 1
                ) else None,
                "html_class": None,
                "l2_field_label": "mock",
                "sample_headwords": [],
                "unique_estimate": total_notes,
                "rationale": "mock — bez wywołania OpenAI",
            }
            _log_import_llm(
                "IMPORT LLM ← RESPONSE (mock)",
                json.dumps(result, ensure_ascii=False, indent=2),
            )
            return result
        result = await self._chat_json(
            self.lookup_model,
            prompt,
            system=IMPORT_STRUCTURE_SYSTEM_V1,
            json_schema=import_structure_schema(),
            max_tokens=2000,
            temperature=0.1,
            purpose="import_structure",
        )
        _log_import_llm(
            "IMPORT LLM ← RESPONSE",
            json.dumps(result, ensure_ascii=False, indent=2),
        )
        return result

    async def verify_card_correction(
        self,
        content: dict[str, Any],
        sections: list[str],
        note: str,
        app_lang: str,
        learning_lang: str,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from app.ai.conjugation import conjugation_paradigm_rules
        from app.lsp.lang_utils import articles_for

        patch_field_names = (
            "lemma",
            "pos",
            "gloss_primary",
            "meanings",
            "examples",
            "conjugation",
            "similar_words",
            "ipa",
            "notes",
            "synonyms_l2",
            "antonyms_l2",
            "word_family_l2",
            "associations_l2",
        )

        lemma = str(content.get("lemma") or "")
        pos = str(content.get("pos") or "")
        conj_guidance = ""
        if pos == "verb" or content.get("conjugation"):
            conj_guidance = (
                "\n\nCONJUGATION VERIFICATION RULES:\n"
                f"{conjugation_paradigm_rules(learning_lang, lemma)}\n"
                "- Reject placeholder dashes, wrong person grids, or missing real forms.\n"
                "- When accepting, patch.conjugation must contain only real inflected forms.\n"
            )
        user_hints = ""
        if sections:
            user_hints += f"User highlighted sections (hints only): {', '.join(sections)}\n"
        if note and note.strip():
            user_hints += f"User note (pay extra attention): {note.strip()}\n"
        if not user_hints:
            user_hints = "User provided no section hints or note.\n"

        article_rule = ""
        if articles_for(learning_lang):
            article_rule = (
                "- For nouns in this learning language, the citation lemma MUST include the "
                "definite article (e.g. 'el intermitente', not 'intermitente'). "
                "A bare noun on the card is a factual error. "
                "Do not require articles for languages that do not use them.\n"
            )
        else:
            article_rule = (
                "- This learning language does not use articles on citation forms; "
                "do not add articles.\n"
            )

        evidence_block = ""
        if evidence:
            evidence_block = (
                "INDEPENDENT DICTIONARY EVIDENCE (Wiktionary). Empty lookup is NOT proof "
                "that a word does not exist.\n"
                f"{json.dumps(evidence, ensure_ascii=False)}\n"
                "If app_lang_page_exists is false for a gloss on the card, that gloss is "
                "likely an invented / non-existent word in the app language — accept and fix it.\n"
            )

        patch_fields = ",".join(f'"{name}"' for name in patch_field_names)
        prompt = (
            "Flashcard correction — FULL CARD AUDIT.\n"
            f"App language: {app_lang}\n"
            f"Learning language: {learning_lang}\n"
            f"{user_hints}"
            "IMPORTANT: Review the ENTIRE card below — lemma, pos, glosses, meanings, "
            "examples, conjugation, similar words, pronunciation, synonyms, antonyms, "
            "word family, associations, notes. "
            "User selections/note are optional hints only; never reject solely because "
            "the note is vague, empty, or off-topic.\n"
            "STRICT ACCEPTANCE RULES:\n"
            "- Accept ONLY a real, clear, significant, noticeable, obvious error: "
            "wrong translation (not a synonym), wrong part of speech, invented/non-existent "
            "word in the app language, missing article where this language uses articles, "
            "placeholder/missing data, or objectively incorrect grammar.\n"
            "- An invented or non-existent word in a family/synonym/antonym gloss is a "
            "factual error — patch word_family_l2 / synonyms_l2 / antonyms_l2 "
            "/ associations_l2.\n"
            "- NEVER accept to replace one valid translation/gloss with another equally valid "
            "alternative (e.g. 'mebel' vs 'obiekt meblowy', 'to speak' vs 'to talk', "
            "'budzić się' vs 'wstawać' when both are correct).\n"
            "- NEVER accept if the card is already correct — return rejected.\n"
            "- content.lemma and the card headword must be the same string.\n"
            f"{article_rule}"
            "- patch must contain ONLY fields that need fixing; omit unchanged fields.\n"
            "- If no factual fix is needed, status must be rejected with code correction_unfounded.\n"
            f"{evidence_block}"
            f"Current card content JSON:\n{json.dumps(content, ensure_ascii=False)}\n"
            f"{conj_guidance}\n"
            "Return JSON only:\n"
            '{"status":"accepted"|"rejected","code":"correction_accepted"|'
            '"correction_unfounded"|"correction_not_applicable",'
            '"reason":"short user-facing summary","reason_detail":"optional admin detail",'
            f'"patch":{{include every field you correct: {patch_fields}}}}}\n'
            "Do not use correction_insufficient_info."
        )
        data = await self._chat_json(
            self.enrichment_model,
            prompt,
            system=(
                "You audit flashcards for factual and linguistic errors only. "
                "Never apply stylistic or synonymous rewordings. "
                "Reject when the card is correct or changes would be equivalent in meaning. "
                "Invented or non-existent words in the app language are factual errors. "
                "Return strict JSON."
            ),
            temperature=0.2,
            purpose="correction",
        )
        status = str(data.get("status", "rejected")).lower()
        if status not in {"accepted", "rejected"}:
            status = "rejected"
        code = str(data.get("code") or "")
        if status == "accepted":
            code = "correction_accepted"
        elif code not in {
            "correction_unfounded",
            "correction_insufficient_info",
            "correction_not_applicable",
        }:
            code = "correction_unfounded"
        return {
            "status": status,
            "code": code,
            "reason": data.get("reason"),
            "reason_detail": data.get("reason_detail") or data.get("reason"),
            "patch": data.get("patch") if isinstance(data.get("patch"), dict) else None,
        }


async def verify_google_id_token(id_token: str) -> dict[str, Any]:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

    aud = data.get("aud")
    if settings.google_client_ids and aud not in settings.google_client_ids:
        raise ValueError("Invalid Google token audience")
    if not data.get("email"):
        raise ValueError("Google token missing email")
    return data
