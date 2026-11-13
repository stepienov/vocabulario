# Vocabulario — Copilot code review

Android + FastAPI app for learning vocabulary. Prefer concrete, high-signal findings over style nits.

## Product invariants (do not break without explicit PR intent)

- `learnable` ≠ `ready`. Practice / flashcards / typing require `learnable` **and** examples present.
- Meanings-first enrichment may show glosses while `examples_pending` is true; status stays `pending`/`preparing` until study finish → then `learnable`.
- Do not move `ready` / `content_is_complete` / `lexical_entries` earlier than full enrichment.
- Import: max **25** items per job and **25** import cards per profile per UTC day; no `import_verify`; profile queue advances after `learnable` (or adaptive write).
- Voice search / mic / STT was removed on purpose. Do not suggest restoring on-device speech or a backend voice endpoint.

## Architecture map

- Backend (FastAPI): `backend/app/` — enrichment in `services/enrichment.py` + `services/card_jobs.py`, import in `services/import_jobs.py` + `api` imports routes.
- Android: `android/app/src/main/java/com/vocabulario/app/` — UI under `ui/`, local Room + API clients under `data/`.
- Specs for recent optimization work: `docs/taski/` (especially 10–12). Treat those as the contract when reviewing related diffs.

## Review focus

- Race / concurrency around card enrichment, SAVEPOINTs, and import queue gating.
- Accidental extra LLM calls, N+1 DB reads, or reintroducing polling loops the tasks removed.
- i18n: every new `strings.xml` key must exist in all 17 locales; CI rejects English copy-paste outside `ALLOW_EN_COPY` in `scripts/check_ui_strings.py`.
- Secrets (`.env`, tokens, DB URLs) must never appear in commits.
- Android UI changes do **not** deploy on Railway; only `backend/` does.

## Validation

CI is `.github/workflows/ci.yml` → `python scripts/ci_check.py` (UI strings, LSP sync, backend pytest). Prefer suggesting that over inventing new check commands.

## Comment style

- Severity-first: bugs, regressions of the invariants above, security, then clarity.
- Skip drive-by refactors unrelated to the diff.
- When suggesting a fix, keep it minimal and aligned with existing patterns in the touched files.
