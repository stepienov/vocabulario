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

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
python run.py
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

Sekrety w pliku `.env` w katalogu głównym repo (nie commituj).

## Struktura

```
vocabulario/
├── android/          # aplikacja Android (Kotlin, Compose)
├── backend/          # API FastAPI
├── infra/            # docker-compose (Postgres + Redis)
└── doc/              # dokumentacja produktowa i techniczna
```

## Flow v0.1

1. Rejestracja / logowanie (email lub Google)
2. **Dodaj słowo** → szukaj w bazie → ewentualnie OpenAI → pełna karta
3. **Ćwicz** → SRS (wybór / wpisz), kierunek L1/L2 w ustawieniach
