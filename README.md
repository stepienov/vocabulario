# Vocabulario

Aplikacja Android do nauki słówek (PL ↔ ES i inne pary) z AI i SRS.

## Szybki start (lokalnie)

### 1. Baza danych

```powershell
cd infra
docker compose up -d
```

Postgres nasłuchuje na **`localhost:5433`** (port 5432 często zajęty przez lokalny PostgreSQL na Windows).

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

Emulator łączy się z API przez `http://10.0.2.2:8000` (już skonfigurowane).

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
├── backend/          # API FastAPI (+ Dockerfile)
├── infra/            # docker-compose (Postgres + Redis)
└── backend/railway.toml  # konfiguracja deploy (Railway)
```


## Flow v0.1

1. Rejestracja / logowanie (email lub Google)
2. **Dodaj słowo** → szukaj w bazie → ewentualnie OpenAI → pełna karta
3. **Ćwicz** → SRS (wybór / wpisz), kierunek L1/L2 w ustawieniach
