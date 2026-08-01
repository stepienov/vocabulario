import json
import re
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.ai.prompts.v1 import (
    LOOKUP_PROMPT_V1,
    LOOKUP_SYSTEM_V1,
    SIMILAR_WORDS_SYSTEM_V1,
    build_conjugation_prompt,
    build_enrichment_core_prompt,
    build_examples_prompt,
    build_similar_words_fill_prompt,
    build_similar_words_prompt,
    lang_name_pl,
)
from app.ai.schemas.similar_words import similar_words_response_schema
from app.core.config import get_settings


class LLMService:
    def __init__(self) -> None:
        settings = get_settings()
        self.mock = settings.llm_mock or not settings.openai_api_key
        self.client = (
            AsyncOpenAI(api_key=settings.openai_api_key) if not self.mock else None
        )
        self.lookup_model = settings.llm_lookup_model
        self.enrichment_model = settings.llm_enrichment_model

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
    ) -> dict[str, Any]:
        if self.mock:
            return self._mock_response(prompt)
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
        if "candidates" in prompt or "kandydat" in prompt.lower():
            return {
                "candidates": [
                    {"lemma": "vacío", "pos": "adj", "gloss": "pusty"},
                    {"lemma": "vaciar", "pos": "verb", "gloss": "opróżniać"},
                ]
            }
        match = re.search(r"Lemat \(L2\):\s*(\S+)", prompt)
        lemma = match.group(1) if match else "palabra"
        return {
            "schema_version": "1.0",
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
            "conjugation": None,
            "notes": None,
            "confidence": 0.95,
        }

    async def lookup(
        self, text: str, native: str, learning: str, cefr: str
    ) -> list[dict[str, Any]]:
        prompt = LOOKUP_PROMPT_V1.format(
            native_name=lang_name_pl(native),
            learning_name=lang_name_pl(learning),
            text=text,
            cefr=cefr,
        )
        data = await self._chat_json(
            self.lookup_model,
            prompt,
            system=LOOKUP_SYSTEM_V1,
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
                "Pracujesz jak słownik dwujęzyczny. Znaczenia podajesz w kolejności "
                "od najczęstszego i każde jest odrębnym sensem — warianty stylistyczne "
                "tego samego sensu idą do synonimów, nie na listę znaczeń. "
                "Peryfrazy gramatyczne (acabar de, ir a, volver a, dejar de) NIE są "
                "znaczeniami lematu — pomijasz je w meanings. "
                "Synonimy mają tę samą część mowy co gloss_l1 (L1) lub lemat (L2). "
                "Bez przykładów i koniugacji. Tylko JSON."
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
                "3 przykłady: jeden A2, jeden B2, jeden C2. Poziomy muszą się wyraźnie "
                "różnić trudnością. Tylko poprawny JSON."
            ),
        )

    async def generate_conjugation(self, lemma: str) -> dict[str, Any] | None:
        prompt = build_conjugation_prompt(lemma=lemma)
        data = await self._chat_json(
            self.enrichment_model,
            prompt,
            system=(
                "Generujesz pełną koniugację czasownika. Periphrases tylko idiomatyczne dla tego lematu "
                "(bez estar/ir + gerundio). Tylko poprawny JSON."
            ),
        )
        conjugation = data.get("conjugation")
        return conjugation if isinstance(conjugation, dict) else None

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
