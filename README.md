# Vocabulario

Aplikacja Android do nauki słówek (PL ↔ ES i inne pary) z AI i SRS.

## Bieżąca praca: przygotowanie bety

**Punkt wyjścia: [E-001 · Beta Google Play](docs/epics/E-001-google-play-beta/README.md).**
To bieżący kierunek pracy, z założeniami biznesowymi, features, zadaniami i kryteriami gotowości — nie deklaracja gotowej aplikacji.

- [Rejestr epików](docs/epics/README.md) i [zasady numeracji](docs/epics/zasady.md) — stały układ epic → feature → task; po zakończeniu zmienia się status, nie lokalizacja.
- [Mapa dokumentacji](docs/README.md) — aktualne instrukcje, referencje i archiwum.
- [Zasady pracy i publikowania](CONTRIBUTING.md) — co trafia do Git, jak aktualizować dokumentację.
- [Katalog skryptów](scripts/README.md) — kontrole CI, narzędzia i operacje utrzymaniowe.
- [E2E](e2e/README.md) — konfiguracja i uruchamianie Maestro.

## Szybki start (lokalnie)

### 1. Baza danych

Domyślnie używamy **lokalnego PostgreSQL** (`localhost:5432`).

```sql
-- jednorazowo (psql -U postgres)
CREATE USER vocabulario WITH PASSWORD 'vocabulario_dev';
CREATE DATABASE vocabulario OWNER vocabulario;
```

Opcjonalnie Docker (Postgres + Redis):

```powershell
cd infra
docker compose up -d
```

Wtedy w `.env` ustaw port **`5433`** w `DATABASE_URL`.

### 2. Backend API

Z katalogu `vocabulario` (jedna komenda):

```powershell
.\start-backend.ps1
```

API: http://localhost:8000/health  
Dokumentacja: http://localhost:8000/docs

### 3. Aplikacja Android

1. Otwórz folder `android/` w **Android Studio**
2. Poczekaj na sync Gradle
3. Uruchom emulator (np. Galaxy_S24)
4. Run ▶

API wybierane automatycznie (Android Studio / Run ▶ = lokalny BE):
- **emulator** → `http://10.0.2.2:8000`
- **fizyczny telefon** → IP z `android/local.properties` (`api.device.host=…`)

APK dla testerów (Railway) — z roota repo, ten sam podpis na obu komputerach:

```powershell
.\build-apk.ps1
```

Wynik: `dist\Vocabulario.apk`. Debug keystore jest w `android/keystore/debug.keystore` (wspólny w gicie).

Szablon: `android/local.properties.example`. Po zmianie hosta zrób Gradle Sync + reinstall appki.

### Konfiguracja

Sekrety w pliku `.env` w katalogu głównym repo (nie commituj). Szablon: `.env.example`.

## Deploy (Railway)

1. Nowy projekt + plugin **PostgreSQL**
2. Serwis z tego repo, **Root Directory = `backend`**
3. Zmienne (minimum):

```
ENVIRONMENT=production
DEBUG=false
JWT_SECRET=<losowy-długi-string, min. 32 znaki>
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MOCK=false
PERSIST_WORDS=true
GOOGLE_OAUTH_CLIENT_ID=<web client ID>
ALLOWED_ORIGINS=<puste albo publiczne https://… po przecinku>
```

`DATABASE_URL` i `PORT` ustawia Railway. Po deployu sprawdź `https://<twoja-domena>/health` (proces żyje) i `https://<twoja-domena>/health/ready` (konfiguracja, schemat i baza). Przy 503 log startu wymienia nazwy błędnych ustawień, bez ich wartości; reguły w [E-001/F-008/T-002](docs/epics/E-001-google-play-beta/features/F-008-jakosc-i-operacje/tasks/T-002-srodowiska-i-konfiguracja.md#postęp).

Status/logi i zasady operacji na produkcji: [Railway CLI](docs/setup/railway-cli.md). Zmiany produkcji wymagają osobnego zlecenia.

## Sprawdzenia

W środowisku z zainstalowanymi zależnościami backendu:

```powershell
python scripts\ci_check.py
```

Komenda sprawdza napisy UI, spójność LSP i testy backendu. Testy oznaczone `pg` wymagają **oddzielnej lokalnej bazy** z `TEST_DATABASE_URL`, o nazwie kończącej się na `_test`; fixture czyści jej tabele. Lokalnie bez bazy są pomijane z ostrzeżeniem, a taki wynik nie potwierdza integracji z bazą. CI uruchamia PostgreSQL i ustawia `REQUIRE_PG_TESTS=1`: brak bazy albo pominięty test `pg` kończy się błędem. Tę samą flagę można ustawić lokalnie. Osobny job CI dla Androida uruchamia `testDebugUnitTest`, `lintDebug` i `assembleDebug` (komenda w [CONTRIBUTING](CONTRIBUTING.md)). Szczegóły: [kontrakt testów PostgreSQL](docs/epics/E-002-szybka-nauka/features/F-001-fundamenty/tasks/T-001-testy-postgresql.md) i [bramki jakości](docs/epics/E-001-google-play-beta/features/F-008-jakosc-i-operacje/tasks/T-001-bramki-jakosci.md).

## Struktura

```
vocabulario/
├── android/          # aplikacja Android (Kotlin, Compose)
├── backend/          # API FastAPI (+ Dockerfile, railway.toml)
├── e2e/              # Maestro E2E
├── infra/            # docker-compose (Postgres + Redis)
├── scripts/          # utrzymywane narzędzia CI, i18n, E2E i backfill
├── docs/             # epiki/features/taski, instrukcje, referencje i audyty
└── .local/           # prywatne notatki i eksperymenty (ignorowane przez Git)
```

Archiwum dokumentacji nadal jest publiczne. `.local/`, sekrety, buildy i surowe raporty nie należą do publikowanej zawartości. Wyjątkiem przejściowym pozostaje opisany wyżej klucz **debug**; klucze produkcyjne nigdy nie trafiają do repozytorium.

## Diagnostyka importu (admin)

Analiza i zapis fiszek żyją w PostgreSQL (`import_jobs`, `import_job_items`, `import_job_events`), nie na telefonie. `users.role = admin` może listować zadania:

```
GET /api/v1/imports/jobs?user_id=&status=&from=&to=
GET /api/v1/imports/jobs/{id}/events
```

Albo SQL:

```sql
SELECT * FROM import_jobs ORDER BY created_at DESC LIMIT 50;
SELECT * FROM import_job_items WHERE job_id = :id ORDER BY ordinal;
SELECT * FROM import_job_events WHERE job_id = :id ORDER BY at;
```

## Flow v0.1

1. Rejestracja / logowanie (email lub Google)
2. **Dodaj słowo** → szukaj w bazie → ewentualnie OpenAI → pełna karta
3. **Ćwicz** → SRS (wybór / wpisz), kierunek L1/L2 w ustawieniach
