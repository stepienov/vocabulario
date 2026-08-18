# Vocabulario

Aplikacja Android do nauki słówek (PL ↔ ES i inne pary) z AI i SRS.

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

APK dla testerów (Railway) — nie zmieniaj `local.properties`:

```powershell
cd android
.\gradlew :app:assembleDebug "-Papi.base.url=https://vocabulario.up.railway.app/api/v1/"
```

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
JWT_SECRET=<losowy-długi-string>
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MOCK=false
PERSIST_WORDS=true
```

`DATABASE_URL` i `PORT` ustawia Railway. Po deployu sprawdź `https://<twoja-domena>/health`.

## Struktura

```
vocabulario/
├── android/          # aplikacja Android (Kotlin, Compose)
├── backend/          # API FastAPI (+ Dockerfile, railway.toml)
├── e2e/              # Maestro E2E
├── infra/            # docker-compose (Postgres + Redis)
├── scripts/          # CI, i18n, e2e
├── docs/             # instalacja APK, epiki, szablon LSP
└── doc/              # notatki robocze (lokalnie, nie na GitHub)
```


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
