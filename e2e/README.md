# E2E (Maestro) — quick start

Plans: `doc/PLAN_TESTY_E2E_INFRA.md`, `doc/PLAN_TESTY_E2E_SCENARIUSZE.md`, `doc/TEST_POLICY.md`.

## Setup

1. Emulator + Maestro (`C:\maestro`) + JDK `C:\Java\jdk-17`
2. Backend: `scripts/start-backend.ps1`
3. Optional for AI flows: `LLM_MOCK=true` in `.env`, restart backend
4. Seed user + cards:

```powershell
.\scripts\e2e-prepare-backend.ps1
```

## Run

```powershell
# Core smoke gate (6 flows, ~4–6 min)
.\scripts\e2e-maestro.ps1

# Full reachable coverage (auth/home/lists/practice/settings/…; slower)
.\scripts\e2e-maestro.ps1 -All

# One family
.\scripts\e2e-maestro.ps1 -Tags settings
.\scripts\e2e-maestro.ps1 -Tags regression
```

If the emulator shows **“Vocabulario isn't responding”**, tap Close / re-run — long suites can ANR a slow AVD. Prefer smoke for day-to-day; `-All` when the machine is free.

## Coverage (reachable UI)

| Area | Flows | Tag |
|---|---|---|
| Auth | A-01, A-03, A-04, A-08, A-09, M-02 | smoke / regression |
| Onboarding | B-01 | regression |
| Home chrome | C-01…C-03, E-03 | smoke / regression |
| Search / add | E-01, E-07 | `ai-mock` (needs `LLM_MOCK`) |
| Import | F-04 cancel; F-01 | regression / `ai-mock` |
| Lists | H-01…H-04 | regression |
| Practice | I-01, I-03, I-05, I-08 | regression (seed cards) |
| Settings | J-01, J-02, J-04, J-05, J-10–13 | regression |
| Languages | K-07 | regression |

**Out of scope for now:** orphan routes (Learning / Profile / Packs), Google Sign-In, SAF file picker, live OpenAI without mock.

Selectors = Compose `testTag` as resource ids. Seed: `POST /api/v1/dev/e2e-seed`.
