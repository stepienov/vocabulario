# Railway CLI — dostęp agenta / lokalny

Produkcja: `https://vocabulario.up.railway.app`  
Root Directory serwisu API: `backend` (patrz `backend/railway.toml`, healthcheck `/health`).

## Po co

Bez CLI agent widzi tylko publiczne HTTP (`/health`, `/docs`) i Postgres przez `PROD_DATABASE_URL`.  
Z CLI + tokenem można: status deployu, logi, zmienne, redeploy, link do projektu.

## Wymagane sekrety (dostarcz do lokalnego `.env`)

| Zmienna | Skąd | Do czego |
|---------|------|----------|
| `RAILWAY_API_TOKEN` | Account Settings → Tokens (**Account / Workspace token**) | `railway whoami`, lista wszystkich projektów |
| `RAILWAY_TOKEN` | **Project** → Settings → Tokens (**Project token**, env = production) | Status/logi/deploy **tego** projektu — u nas to wystarczy |
| `RAILWAY_PROJECT_ID` | Project → Settings → General (opcjonalnie, ułatwia skryptom) | Identyfikacja projektu bez `railway link` |
| `RAILWAY_SERVICE_ID` | Service → Settings (opcjonalnie) | Konkretny serwis API |
| `RAILWAY_ENVIRONMENT` | zwykle `production` | Wybór środowiska |

`PROD_DATABASE_URL` już jest w `.env` — to osobny dostęp do PG, nie zastępuje CLI.

**Nie commituj tokenów.** Szablon: `.env.example`.

## Instalacja CLI (Windows)

Na tej maszynie działa ścieżka przez **Node + npm** (Node 22 z winget):

```powershell
winget install -e --id OpenJS.NodeJS.22
npm i -g @railway/cli
# nowa sesja terminala, potem:
railway --version   # np. railway 5.71.0
```

Alternatywa (Scoop):

```powershell
scoop bucket add railway https://github.com/railwayapp/scoop-railway
scoop install railway/railway
```

**Uwaga WDAC:** surowy `railway.exe` z GitHub Releases wrzucony do `%LOCALAPPDATA%\railway\bin` bywał blokowany („Zasady kontroli aplikacji zablokowały ten plik”). Nie trzymaj tego katalogu na początku `PATH` — wtedy `where railway` wskazywał martwy binary zamiast shimu npm (`%APPDATA%\npm\railway.cmd`). Shim npm woła `railway.js` i działa.

## Auth (jednorazowo)

Interaktywnie (przeglądarka):

```powershell
railway login
```

Bez przeglądarki / dla agenta — token w env:

```powershell
# Project token (zalecane dla Vocabulario):
$env:RAILWAY_TOKEN = "..."
$env:RAILWAY_ENVIRONMENT = "production"
railway status
railway service list
railway deployment list -s vocabulario
railway logs -s vocabulario -n 50

# Account token (opcjonalnie, do whoami / list wszystkich projektów):
$env:RAILWAY_API_TOKEN = "..."
railway whoami
```

Uwaga: token z **Project → Tokens** musi być w `RAILWAY_TOKEN`. W `RAILWAY_API_TOKEN` Railway zwraca Unauthorized.

Potem w repo (jednorazowo):

```powershell
cd C:\Users\Usuario\Desktop\vocabulario
railway link   # wybierz projekt Vocabulario + środowisko production + serwis backend
```

Albo bez linku, z ID:

```powershell
railway status --project <RAILWAY_PROJECT_ID> --environment production
```

## Typowe komendy agenta

```powershell
railway whoami
railway status
railway service status
railway deployment list
railway logs --tail 100
railway variables
# redeploy ostatniego / trigger
railway redeploy --yes
```

Smoke bez CLI:

```powershell
Invoke-RestMethod https://vocabulario.up.railway.app/health
```

## Checklist „czy deploy z main wjechał”

1. `git rev-parse origin/main`
2. `railway deployment list` — SHA / czas ostatniego successful
3. `GET https://vocabulario.up.railway.app/health` → `status=ok`, `environment=production`
4. Brak `error`/`critical` w `app_logs` (Postgres) w oknie po deployu

Uwaga: `/health` **nie zwraca git SHA** — bez CLI nie da się 1:1 potwierdzić commita na kontenerze.

## Regiony (odczyt 8 listopada 2026)

`railway status --json`, środowisko production:

| Serwis | Repliki | Region |
|---|---|---|
| `vocabulario` (API) | 2, obie RUNNING | `europe-west4-drams3a` × 1 i `us-west2` × 1 |
| `Postgres` | 1, RUNNING | działająca instancja w starszym `sfo` |

`DATABASE_URL` serwisu API wskazuje host `postgres.railway.internal`. Publiczny proxy bazy istnieje, API go nie używa.

Docelowo API ma jedną replikę w `us-west2`. To jest w `backend/railway.toml` i wchodzi dopiero przy deployu z `main`. `sfo` nie jest już poprawnym identyfikatorem regionu (`us-west2`, `us-east4-eqdc4a`, `europe-west4-drams3a`, `asia-southeast1-eqsg3a`). Wpisanie `sfo` blokuje deploy. Redeploy serwisu Postgres przeniósłby wolumen z `sfo` do nowego regionu i zatrzymał bazę na czas migracji. Tego serwisu nie zmieniamy.

## Co agent ma robić

- Przed diagnozą prod: sprawdź `railway --version` i `RAILWAY_API_TOKEN` / `RAILWAY_TOKEN`.
- Nie loguj pełnych tokenów do czatu ani commitów.
- Android (`BlockingBusy` itd.) **nie** deployuje się na Railway — tylko `backend/`.
