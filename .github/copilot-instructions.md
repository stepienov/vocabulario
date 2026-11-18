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
- Optimization contracts live in `docs/epics/E-002-szybka-nauka/`: especially E-002/F-004/T-003 (study/related), E-002/F-005/T-001 (import), E-002/F-004/T-004 (early meanings). Legacy task numbers 10–12 map through `docs/epics/migracja.md`.

## Current work and repository hygiene

- `docs/epics/README.md` is the topic registry; current priority is `docs/epics/E-001-google-play-beta/README.md`. Follow `docs/epics/zasady.md`: epic → feature → optional tasks, stable paths and hierarchical IDs such as E-001/F-004/T-001.
- Keep completed epics in place and update status/evidence, never archive or renumber them. Dated analyses in each epic's `sources/` are evidence, not a second live backlog. Historical findings F-01…F-16 are not feature IDs.
- Follow `CONTRIBUTING.md` for publication rules. Keep one-off probes, raw reports and machine-specific notes in ignored `.local/`, not in public documentation or application directories.
- `docs/archive/` is public historical context, not a second active roadmap. Do not restart old optimization tasks merely because their specifications remain in the repository.

## Review focus

- Race / concurrency around card enrichment, SAVEPOINTs, and import queue gating.
- Accidental extra LLM calls, N+1 DB reads, or reintroducing polling loops the tasks removed.
- i18n: every new `strings.xml` key must exist in all 17 locales; CI rejects English copy-paste outside `ALLOW_EN_COPY` in `scripts/check_ui_strings.py`.
- Secrets (`.env`, tokens, DB URLs) must never appear in commits.
- Android UI changes do **not** deploy on Railway; only `backend/` does.

## APK distribution

- After a successful, verified APK build, keep only the newest APK in `dist/`, named `Vocabulario.apk`; remove older APKs from that folder.

## Validation

CI is `.github/workflows/ci.yml` → `python scripts/ci_check.py` (UI strings, LSP sync, backend pytest). Prefer suggesting that over inventing new check commands.

## Comment style

- Severity-first: bugs, regressions of the invariants above, security, then clarity.
- Skip drive-by refactors unrelated to the diff.
- When suggesting a fix, keep it minimal and aligned with existing patterns in the touched files.
