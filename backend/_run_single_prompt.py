import asyncio
import json
import os
import time
from pathlib import Path

from app.services.llm import LLMService


PROMPT = '''Język 1: {language_1}
Język 2: {language_2}
Hasło: "{query}"

Sprawdź, czy hasło zapisane dokładnie znak w znak
jest samodzielnym słowem w którymkolwiek z podanych języków.

Nie poprawiaj, nie normalizuj i nie usuwaj żadnych znaków.
Nie uwzględniaj odmian, literówek ani podobnych słów.
W polu language skopiuj dokładnie nazwę jednego z podanych języków.

Zwróć wyłącznie JSON:
{{
  "words": [
    {{
      "word": "{query}",
      "language": "...",
      "dictionary_entries": [
        {{
          "dictionary_form": "...",
          "part_of_speech": "...",
          "translations_to_other_language": ["..."]
        }}
      ]
    }}
  ]
}}'''

async def main() -> None:
    llm = LLMService()
    fixture = json.loads(
        Path("../docs/testy-requestow/exact-headword-cases.json").read_text(
            encoding="utf-8"
        )
    )
    cases = [
        (case, set(case["expected_languages"]))
        for case in fixture["positive_homographs"]
    ] + [(case, set()) for case in fixture["negative_exact_strings"]]
    query_filter = os.environ.get("EXACT_QUERY")
    if query_filter:
        wanted = {value.strip() for value in query_filter.split(",") if value.strip()}
        cases = [case for case in cases if case[0]["query"] in wanted]
    cases *= int(os.environ.get("EXACT_REPEAT", "1"))
    repeat_queries = {
        value.strip()
        for value in os.environ.get("EXACT_REPEAT_QUERIES", "").split(",")
        if value.strip()
    }
    if repeat_queries:
        extra = [
            case
            for case in cases
            if case[0]["query"] in repeat_queries
            for _ in range(3)
        ]
        cases += extra
    model = "gpt-6-luna"
    reasoning_effort = os.environ.get("EXACT_REASONING", "none")
    service_tier = os.environ.get("EXACT_SERVICE_TIER", "auto")
    passed = 0
    for case, expected in cases:
            language_1 = case["language_1"]
            language_2 = case["language_2"]
            query = case["query"]
            prompt = PROMPT.format(
                language_1=language_1,
                language_2=language_2,
                query=query,
            )
            started = time.perf_counter()
            response = await llm.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_completion_tokens=1200,
                reasoning_effort=reasoning_effort,
                service_tier=service_tier,
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
            actual = {
                str(item.get("language") or "").casefold()
                for item in data.get("words") or []
                if isinstance(item, dict)
            }
            ok = actual == expected
            passed += int(ok)
            print(
                json.dumps(
                    {
                        "ok": ok,
                        "pair": f"{language_1}>{language_2}",
                        "query": query,
                        "elapsed_ms": elapsed_ms,
                        "expected": sorted(expected),
                        "actual": sorted(actual),
                        "response": data,
                    },
                    ensure_ascii=False,
                )
            )
    print(json.dumps({"passed": passed, "total": len(cases)}))


asyncio.run(main())
