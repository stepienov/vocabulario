import json
import logging
import re
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.ai.prompts.v1 import (
    IMPORT_ADAPTIVE_PROMPT_V1,
    IMPORT_ADAPTIVE_SYSTEM_V1,
    IMPORT_ANSWER_STRUCTURE_PROMPT_V1,
    IMPORT_ANSWER_STRUCTURE_SYSTEM_V1,
    IMPORT_CLASSIFY_PROMPT_V1,
    IMPORT_CLASSIFY_SYSTEM_V1,
    IMPORT_DISPLAY_PROMPT_V1,
    IMPORT_DISPLAY_SYSTEM_V1,
    IMPORT_FORMAT_PROMPT_V1,
    IMPORT_FORMAT_SYSTEM_V1,
    IMPORT_LAYOUT_PROMPT_V1,
    IMPORT_LAYOUT_SYSTEM_V1,
    IMPORT_STRUCTURE_SYSTEM_V1,
    LOOKUP_L1_TYPO_PROMPT_V1,
    LOOKUP_PROMPT_V1,
    LOOKUP_SYSTEM_V1,
    lookup_output_form_rules_text,
    SIMILAR_WORDS_SYSTEM_V1,
    build_enrichment_core_prompt,
    build_examples_prompt,
    build_similar_words_fill_prompt,
    build_similar_words_prompt,
)
from app.ai.language_typology import lang_name_en, language_pair_guidance
from app.ai.schemas.import_classify import (
    import_adaptive_enrich_schema,
    import_classify_schema,
)
from app.ai.schemas.import_display import (
    import_answer_structure_schema,
    import_display_schema,
    validate_import_display_payload,
)
from app.ai.schemas.import_format import import_format_schema
from app.ai.schemas.import_structure import import_structure_schema
from app.ai.schemas.similar_words import similar_words_response_schema
from app.core.config import get_settings

logger = logging.getLogger(__name__)


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
            AsyncOpenAI(api_key=settings.openai_api_key) if not self.mock else None
        )
        self.lookup_model = settings.llm_lookup_model
        self.enrichment_model = settings.llm_enrichment_model
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
    ) -> dict[str, Any]:
        if self.mock:
            return self._mock_response(prompt)
        use_provider = (provider or "openai").strip().lower()
        if use_provider == "anthropic" and self._anthropic is not None:
            return await self._chat_json_anthropic(
                model,
                prompt,
                system,
                json_schema=json_schema,
                max_tokens=max_tokens,
            )
        assert self.client is not None
        system_content = system or (
            "Jesteś asystentem językowym. Zwracasz wyłącznie poprawny JSON "
            "bez markdown i bez komentarzy."
        )
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
        }
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
        response = await self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    async def _chat_json_anthropic(
        self,
        model: str,
        prompt: str,
        system: str | None,
        *,
        json_schema: dict | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
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
        return json.loads(text or "{}")

    def _mock_similar_words(self, lemma: str) -> list[dict[str, str]]:
        """Dystraktory — inne słowa, nie odmiany lematu."""
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
        base = lemma[:4] if len(lemma) >= 4 else lemma
        variants = [
            (f"ab{base[-2:]}", "verb", "gasić"),
            (f"ac{base[-2:]}", "verb", "przyklejać"),
            (f"ad{base[-2:]}", "verb", "układać"),
            (f"al{base[-2:]}", "verb", "stosować"),
            (f"am{base[-2:]}", "verb", "stawiać"),
            (f"an{base[-2:]}", "verb", "wskazywać"),
            (f"as{base[-2:]}", "verb", "wnosić"),
            (f"at{base[-2:]}", "verb", "zatwierdzać"),
            (f"av{base[-2:]}", "verb", "parować"),
            (f"az{base[-2:]}", "verb", "ściskać"),
            (f"ag{base[-2:]}", "verb", "oddawać"),
            (f"aj{base[-2:]}", "verb", "odwoływać"),
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
            count_match = re.search(r"Podaj (\d+) słów", prompt)
            count = int(count_match.group(1)) if count_match else 12
            exclude_match = re.search(r"Żadne nie może być na tej liście: (.+)", prompt)
            excluded = set()
            if exclude_match:
                excluded = {
                    word.strip().lower()
                    for word in exclude_match.group(1).split(",")
                    if word.strip() and word.strip() != "(brak)"
                }
            pool = self._mock_similar_words("palabra")
            filtered = [i for i in pool if i["lemma"].lower() not in excluded]
            return {"similar_words": filtered[:count]}
        if "Słowo na fiszce:" in prompt:
            match = re.search(r"Słowo na fiszce:\s*(\S+)", prompt)
            lemma = match.group(1).rstrip(".”„") if match else "palabra"
            return {"similar_words": self._mock_similar_words(lemma)}
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
                        {"l2": f"Ejemplo con {lemma}.", "l1": "Przykład.", "cefr": "A2"},
                        {"l2": f"Otro {lemma}.", "l1": "Inny przykład.", "cefr": "A1"},
                    ],
                    "usages": [],
                }
            ],
            "synonyms_l2": [],
            "antonyms_l2": [],
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
        data = await self._chat_json(
            self.lookup_model,
            prompt,
            system=LOOKUP_SYSTEM_V1,
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
        )
        return data.get("candidates", [])

    async def enrich_core(
        self,
        lemma: str,
        pos: str | None,
        native: str,
        learning: str,
        cefr: str,
    ) -> dict[str, Any]:
        prompt = build_enrichment_core_prompt(
            native=native,
            learning=learning,
            lemma=lemma,
            pos=pos or "unknown",
            cefr=cefr,
        )
        return await self._chat_json(
            self.lookup_model,
            prompt,
            system=(
                "You work like a bilingual dictionary. Meanings in frequency order; "
                "stylistic variants of the same sense go to synonyms, not meanings. "
                "Periphrases belong to THIS L2 only (never invent Spanish acabar de / ir a "
                "for other L2) and are NOT lemma meanings — omit them from meanings. "
                "Synonyms/antonyms must match POS of the lemma; same-root derivatives go to "
                "word_family_l2 (other POS allowed), not synonyms. "
                "No examples, no conjugation. JSON only."
            ),
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
        return await self._chat_json(
            self.lookup_model,
            prompt,
            system=(
                "Generujesz przykłady zdań. Dla każdego znaczenia MUSISZ zwrócić dokładnie "
                "3 zdania: jedno A2, jedno B2, jedno C2. Poziomy muszą się wyraźnie "
                "różnić trudnością. ZAKAZ powtarzania tego samego zdania l2 między "
                "znaczeniami. Tylko poprawny JSON."
            ),
        )

    async def generate_lsp_inflection(self, prompt: str) -> dict[str, Any]:
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
        return await self._chat_json(self.enrichment_model, prompt)

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
        prompt = build_similar_words_prompt(
            native=native,
            learning=learning,
            lemma=lemma,
            pos=pos_val,
            count=count,
        )
        data = await self._chat_json(
            self.lookup_model,
            prompt,
            system=SIMILAR_WORDS_SYSTEM_V1,
            json_schema=similar_words_response_schema(count=count),
            max_tokens=4000,
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
            self.lookup_model,
            prompt,
            system=SIMILAR_WORDS_SYSTEM_V1,
            json_schema=similar_words_response_schema(count=count),
            max_tokens=4000,
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
        )
        _log_import_llm(
            "IMPORT CLASSIFY ← RESPONSE",
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
        return await self._chat_json(
            self.lookup_model,
            prompt,
            system=IMPORT_ADAPTIVE_SYSTEM_V1,
            json_schema=import_adaptive_enrich_schema(),
            max_tokens=3500,
            temperature=0.2,
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
        )
        _log_import_llm(
            "IMPORT LLM ← RESPONSE",
            json.dumps(result, ensure_ascii=False, indent=2),
        )
        return result

    async def analyze_import_display(
        self,
        *,
        native: str,
        learning: str,
        kind: str,
        field_names: list[str] | None,
        sample_notes: list[list[str]],
        total_notes: int,
    ) -> dict:
        """Mapa ról pól + szablon bloków UI (front/back) dla trybu preserve."""
        compact = []
        for note in sample_notes:
            row = []
            for cell in note:
                row.append(cell[:400] if "<" in cell else cell)
            compact.append(row)
        prompt = IMPORT_DISPLAY_PROMPT_V1.format(
            native_name=lang_name_en(native),
            learning_name=lang_name_en(learning),
            kind=kind,
            total_notes=total_notes,
            field_names=json.dumps(field_names, ensure_ascii=False)
            if field_names
            else "nieznane",
            sample_json=json.dumps(compact, ensure_ascii=False, indent=2),
        )
        _log_import_llm(
            f"IMPORT DISPLAY → PROMPT (model={self.lookup_model}, kind={kind})",
            f"--- SYSTEM ---\n{IMPORT_DISPLAY_SYSTEM_V1}\n\n--- USER ---\n{prompt}",
        )
        result = await self._chat_json(
            self.lookup_model,
            prompt,
            system=IMPORT_DISPLAY_SYSTEM_V1,
            json_schema=import_display_schema(),
            max_tokens=3500,
            temperature=0.1,
        )
        _log_import_llm(
            "IMPORT DISPLAY ← RESPONSE",
            json.dumps(result, ensure_ascii=False, indent=2),
        )
        return result

    async def analyze_import_layout(
        self,
        *,
        native: str,
        learning: str,
        kind: str,
        field_names: list[str] | None,
        sample_notes: list[list[str]],
        total_notes: int,
    ) -> dict:
        """One-shot layout analysis for preserve import (display v2).

        Uses llm_import_layout_model / llm_import_provider. Validates output;
        raises ValueError on invalid payload so caller can fall back to heuristics.
        """
        compact = []
        for note in sample_notes:
            row = []
            for cell in note:
                row.append(cell[:800] if "<" in cell else cell)
            compact.append(row)
        prompt = IMPORT_LAYOUT_PROMPT_V1.format(
            native_name=lang_name_en(native),
            learning_name=lang_name_en(learning),
            kind=kind,
            total_notes=total_notes,
            field_names=json.dumps(field_names, ensure_ascii=False)
            if field_names
            else "nieznane",
            sample_json=json.dumps(compact, ensure_ascii=False, indent=2),
        )
        model = self.import_layout_model
        provider = self.import_provider
        _log_import_llm(
            f"IMPORT LAYOUT → PROMPT (model={model}, provider={provider}, kind={kind})",
            f"--- SYSTEM ---\n{IMPORT_LAYOUT_SYSTEM_V1}\n\n--- USER ---\n{prompt}",
        )

        last_err: Exception | None = None
        for attempt in range(2):
            try:
                result = await self._chat_json(
                    model,
                    prompt,
                    system=IMPORT_LAYOUT_SYSTEM_V1,
                    json_schema=import_display_schema(),
                    max_tokens=4500,
                    temperature=0.1,
                    provider=provider,
                )
                ok, reason = validate_import_display_payload(result)
                if not ok:
                    raise ValueError(f"invalid import layout payload: {reason}")
                if "bidirectional" not in result:
                    result["bidirectional"] = False
                _log_import_llm(
                    f"IMPORT LAYOUT ← RESPONSE (attempt={attempt + 1})",
                    json.dumps(result, ensure_ascii=False, indent=2),
                )
                return result
            except Exception as exc:
                last_err = exc
                logger.warning("import layout attempt %s failed: %s", attempt + 1, exc)
        raise ValueError(f"import layout failed: {last_err}") from last_err

    async def analyze_import_answer_structure(
        self,
        *,
        native: str,
        learning: str,
        samples: list[str],
    ) -> dict:
        """Jak podzielić grubą prawą stronę na sekcje/bloki."""
        prompt = IMPORT_ANSWER_STRUCTURE_PROMPT_V1.format(
            native_name=lang_name_en(native),
            learning_name=lang_name_en(learning),
            samples_json=json.dumps(samples, ensure_ascii=False, indent=2),
        )
        _log_import_llm(
            "IMPORT ANSWER STRUCTURE → PROMPT",
            f"--- SYSTEM ---\n{IMPORT_ANSWER_STRUCTURE_SYSTEM_V1}\n\n--- USER ---\n{prompt}",
        )
        result = await self._chat_json(
            self.lookup_model,
            prompt,
            system=IMPORT_ANSWER_STRUCTURE_SYSTEM_V1,
            json_schema=import_answer_structure_schema(),
            max_tokens=3000,
            temperature=0.1,
        )
        _log_import_llm(
            "IMPORT ANSWER STRUCTURE ← RESPONSE",
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
    ) -> dict[str, Any]:
        from app.ai.conjugation import conjugation_paradigm_rules

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

        prompt = (
            "Flashcard correction — FULL CARD AUDIT.\n"
            f"App language: {app_lang}\n"
            f"Learning language: {learning_lang}\n"
            f"{user_hints}"
            "IMPORTANT: Review the ENTIRE card below — lemma, pos, glosses, meanings, "
            "examples, conjugation, similar words, pronunciation. "
            "User selections/note are optional hints only; never reject solely because "
            "the note is vague, empty, or off-topic.\n"
            "STRICT ACCEPTANCE RULES:\n"
            "- Accept ONLY when there is a factual error, clear omission, wrong translation, "
            "wrong part of speech, placeholder/missing data, or objectively incorrect grammar.\n"
            "- NEVER accept to replace one valid translation/gloss with another equally valid "
            "alternative (e.g. 'mebel' vs 'obiekt meblowy', 'to speak' vs 'to talk').\n"
            "- NEVER accept if the card is already correct — return rejected.\n"
            "- patch must contain ONLY fields that need fixing; omit unchanged fields.\n"
            "- If no factual fix is needed, status must be rejected with code correction_unfounded.\n"
            f"Current card content JSON:\n{json.dumps(content, ensure_ascii=False)}\n"
            f"{conj_guidance}\n"
            "Return JSON only:\n"
            '{"status":"accepted"|"rejected","code":"correction_accepted"|'
            '"correction_unfounded"|"correction_not_applicable",'
            '"reason":"short user-facing summary","reason_detail":"optional admin detail",'
            '"patch":{include every field you correct: '
            '"lemma","pos","gloss_primary","meanings","examples","conjugation","similar_words","ipa"}}\n'
            "Do not use correction_insufficient_info."
        )
        data = await self._chat_json(
            self.enrichment_model,
            prompt,
            system=(
                "You audit flashcards for factual and linguistic errors only. "
                "Never apply stylistic or synonymous rewordings. "
                "Reject when the card is correct or changes would be equivalent in meaning. "
                "Return strict JSON."
            ),
            temperature=0.2,
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

    async def validate_self_edit_changes(
        self,
        *,
        lemma: str,
        learning_lang: str,
        app_lang: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = (
            "Validate a user's manual flashcard edits before saving.\n"
            f"Lemma (L2): {lemma}\n"
            f"Learning language: {learning_lang}\n"
            f"App/UI language: {app_lang}\n"
            f"User changes JSON:\n{json.dumps(changes, ensure_ascii=False)}\n"
            "Review ONLY the user's changes (the 'to' values). "
            "Flag factual or linguistic errors, wrong POS, mistranslations, or nonsense. "
            "Do NOT flag stylistic preferences or minor wording differences.\n"
            "Return JSON only:\n"
            '{"ok":true|false,"issues":[{"field":"pos|notes|meanings[0].gloss_l1|...","label":"short label in app language","message":"why it is wrong in app language"}]}\n'
            "If all changes are reasonable, return ok:true with empty issues. "
            "List ONLY changes that are actually incorrect."
        )
        if self.mock:
            issues: list[dict[str, str]] = []
            changes_json = json.dumps(changes, ensure_ascii=False).lower()
            if "invalid" in changes_json or "dupa" in changes_json:
                issues.append(
                    {
                        "field": "meanings[0].gloss_l1",
                        "label": "Główne tłumaczenie" if app_lang.startswith("pl") else "Primary gloss",
                        "message": (
                            "To tłumaczenie wygląda na nieprawidłowe."
                            if app_lang.startswith("pl")
                            else "This gloss looks incorrect."
                        ),
                    }
                )
            return {"ok": not issues, "issues": issues}

        data = await self._chat_json(
            self.enrichment_model,
            prompt,
            system=(
                "You validate user flashcard edits. Be strict on factual errors, lenient on style. "
                "Return strict JSON."
            ),
            temperature=0.2,
        )
        ok = bool(data.get("ok", True))
        raw_issues = data.get("issues") if isinstance(data.get("issues"), list) else []
        issues = []
        for item in raw_issues:
            if not isinstance(item, dict):
                continue
            field = str(item.get("field") or "").strip()
            label = str(item.get("label") or field).strip()
            message = str(item.get("message") or "").strip()
            if field and message:
                issues.append({"field": field, "label": label, "message": message})
        if issues:
            ok = False
        return {"ok": ok, "issues": issues}

    async def review_self_edit(
        self,
        *,
        before_content: dict[str, Any],
        after_content: dict[str, Any],
        before_lemma: str,
        after_lemma: str,
        app_lang: str,
        learning_lang: str,
    ) -> dict[str, Any]:
        prompt = (
            "Review a user's manual flashcard edit.\n"
            f"App language: {app_lang}\n"
            f"Learning language: {learning_lang}\n"
            f"Before lemma: {before_lemma}\n"
            f"After lemma: {after_lemma}\n"
            f"Before content JSON:\n{json.dumps(before_content, ensure_ascii=False)}\n"
            f"After content JSON:\n{json.dumps(after_content, ensure_ascii=False)}\n"
            "Return JSON only:\n"
            '{"verdict":"self_edit_ok"|"self_edit_questionable"|"self_edit_invalid",'
            '"reason":"short explanation for admin"}\n'
            "Do not block the user — this is for admin review only."
        )
        data = await self._chat_json(
            self.enrichment_model,
            prompt,
            system="You review whether a user's flashcard edit is linguistically reasonable. Return strict JSON.",
            temperature=0.2,
        )
        verdict = str(data.get("verdict", "self_edit_questionable"))
        if verdict not in {"self_edit_ok", "self_edit_questionable", "self_edit_invalid"}:
            verdict = "self_edit_questionable"
        return {"verdict": verdict, "reason": data.get("reason")}


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
