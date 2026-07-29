# Vocabulario — plan implementacji (techniczny)

Dokument inżynierski. Cel: na jego podstawie da się zbudować **w pełni działającą, kompletną i stabilną** aplikację. Rozbity na fazy, z konkretną technologią, bibliotekami, usługami zewnętrznymi, kontraktami API, schematem bazy, testami i wdrożeniem.

> Powiązany dokument produktowy: [`PLAN_APLIKACJI.md`](./PLAN_APLIKACJI.md). Ten plik jest jego technicznym rozwinięciem.

---

## 0. Zasady prowadzenia projektu

- **Monorepo** (jedno repo `vocabulario`, wiele katalogów) — łatwiejsze wspólne wersjonowanie kontraktów.
- **Kontrakt API najpierw** (OpenAPI) → z niego generujemy typy dla klienta Androida.
- **Testy na każdą warstwę** (unit + integration + e2e), CI blokuje merge przy czerwonych testach.
- **Migracje bazy wersjonowane** (Alembic) — nigdy ręczne zmiany schematu.
- **Feature flags** dla rzeczy z dalszych release’ów (teacher, speech, conjugación drills).
- **12-factor**: konfiguracja przez zmienne środowiskowe, brak sekretów w repo.
- **Definition of Done** dla każdej fazy: kod + testy + migracje + dokumentacja + zielone CI.

### Struktura repo (docelowa)

```
vocabulario/
├── doc/                      # dokumentacja (ten plik, plan produktowy)
├── backend/                  # FastAPI
│   ├── app/
│   │   ├── api/              # routery (auth, lookup, cards, srs, decks, teacher)
│   │   ├── core/             # config, security, deps
│   │   ├── db/               # sesja, base, migracje (alembic/)
│   │   ├── models/           # SQLAlchemy ORM
│   │   ├── schemas/          # Pydantic (request/response)
│   │   ├── services/         # logika: srs, ai, tts, auth
│   │   ├── ai/               # klient LLM, prompty, walidacja JSON
│   │   └── main.py
│   ├── tests/
│   ├── alembic/
│   ├── pyproject.toml
│   └── Dockerfile
├── android/                  # aplikacja Android (Kotlin, Compose)
│   ├── app/
│   │   └── src/main/java/.../ (ui, data, domain, di)
│   └── build.gradle.kts
├── teacher-web/              # panel nauczyciela (release v0.3) — Next.js
├── infra/                    # docker-compose, IaC, skrypty deploy
│   └── docker-compose.yml
├── .github/workflows/        # CI/CD
└── README.md
```

---

## 1. Architektura wysokopoziomowa

```
                         ┌───────────────────────────────────────┐
                         │              Klienci                   │
   Android (Compose)  ───┤  Room (offline cards + SRS state)      │
   Teacher Web (Next)  ──┤                                        │
                         └───────────────────┬───────────────────┘
                                             │ HTTPS / JSON (REST)
                                             ▼
                         ┌───────────────────────────────────────┐
                         │            FastAPI (backend)           │
                         │  auth · lookup · cards · srs · decks   │
                         │  teacher · audio-meta · sync           │
                         └───┬───────────┬───────────┬───────────┘
                             │           │           │
                 ┌───────────▼──┐  ┌─────▼─────┐  ┌──▼───────────┐
                 │ PostgreSQL   │  │  Redis    │  │  LLM provider│
                 │ (źródło      │  │ cache +   │  │  (OpenAI /   │
                 │  prawdy)     │  │ kolejki   │  │  Anthropic)  │
                 └──────────────┘  └───────────┘  └──────────────┘
                                        │
                                 ┌──────▼───────┐
                                 │ Worker (RQ / │  enrichment async,
                                 │ Celery/arq)  │  prefetch TTS
                                 └──────────────┘
```

- **Źródło prawdy:** PostgreSQL.
- **Cache i kolejki:** Redis (cache lookup/enrichment + zadania w tle).
- **Worker:** przetwarza ciężki enrichment i prefetch audio poza request/response (żeby lookup był szybki).
- **Android** trzyma lokalną kopię kart + stan SRS w Room → nauka offline, sync przy sieci.
- **TTS w v0.1:** systemowe TTS Androida (bez kosztów, offline). Cloud TTS = późniejszy release, wtedy backend generuje/proxuje audio.

---

## 2. Stack technologiczny (konkretnie)

### 2.1 Backend

| Element | Wybór | Uwagi |
|--------|-------|------|
| Język | Python 3.12 | |
| Framework | **FastAPI** | async, OpenAPI out-of-the-box |
| Serwer ASGI | **Uvicorn** (za Gunicorn w prod) | |
| ORM | **SQLAlchemy 2.x** (async) | |
| Migracje | **Alembic** | |
| Walidacja / DTO | **Pydantic v2** | |
| Auth | **python-jose** (JWT) + **passlib[bcrypt]** | hash haseł |
| Google OAuth | **Authlib** lub weryfikacja id_token Google | |
| Cache/kolejka | **Redis** + **arq** (async worker) | arq lekki, async-friendly |
| Klient LLM | oficjalny SDK **openai** i/lub **anthropic** | abstrakcja providera |
| HTTP klient | **httpx** | |
| Rate limiting | **slowapi** / limiter na Redis | ochrona endpointów AI |
| Testy | **pytest**, **pytest-asyncio**, **httpx AsyncClient**, **testcontainers** (Postgres) | |
| Lint/format | **ruff**, **black**, **mypy** | |
| Logi | **structlog** (JSON logs) | |
| Config | **pydantic-settings** (.env) | |

### 2.2 Android

| Element | Wybór |
|--------|-------|
| Język | Kotlin |
| UI | **Jetpack Compose** + Material 3 |
| Architektura | MVVM + **Clean-ish** (ui / domain / data) |
| DI | **Hilt** |
| Async | Coroutines + **Flow** |
| Sieć | **Retrofit** + **OkHttp** + **kotlinx.serialization** (Kotlin Serialization Converter) |
| Lokalna baza | **Room** (offline cards + SRS) |
| Ustawienia | **DataStore** (Preferences) |
| Nawigacja | **Navigation-Compose** |
| Auth Google | **Credential Manager** + Google ID (nowe API) |
| TTS | **android.speech.tts.TextToSpeech** (systemowe) |
| Speech-to-text (v0.2) | **SpeechRecognizer** (systemowe) |
| Obrazy/ikony | Material Icons, Coil (jeśli obrazy) |
| Testy | JUnit, **Turbine** (Flow), Compose UI test, **MockWebServer** |
| Praca w tle / sync | **WorkManager** |
| Powiadomienia (późniejszy release) | WorkManager + Notification API / FCM |

### 2.3 Teacher web (v0.3)

| Element | Wybór |
|--------|-------|
| Framework | **Next.js (React, TypeScript)** |
| UI | Tailwind + shadcn/ui |
| Auth | ten sam backend (JWT / OAuth), rola `teacher` |
| Wykresy postępów | Recharts |

### 2.4 DevOps

| Element | Wybór |
|--------|-------|
| Konteneryzacja | Docker + docker-compose (lokalnie) |
| Hosting API+DB | **Railway** lub **Fly.io** (Postgres + Redis managed) — szybki start |
| CI/CD | **GitHub Actions** |
| Sekrety | GitHub Secrets / zmienne środowiskowe hostingu |
| Monitoring | Sentry (błędy) + healthcheck endpoint |
| Migracje w deploy | Alembic w kroku release |

---

## 3. Usługi zewnętrzne (external services)

| Usługa | Do czego | v0.1? | Uwaga / koszt |
|--------|----------|-------|---------------|
| **LLM API** (OpenAI GPT-4o-mini / Anthropic Claude Haiku do lookup; większy model do enrichment) | wykrywanie języka, kandydaci, budowa karty (structured JSON) | **TAK — kluczowe** | płatne per token; cache mocno ogranicza koszt |
| **PostgreSQL** (managed: Railway/Fly/Supabase) | źródło prawdy | TAK | |
| **Redis** (managed) | cache + kolejki | TAK (może być in-memory na start dev) | |
| **Google OAuth / Identity** | logowanie Google | TAK | darmowe |
| **Android system TTS** | wymowa | TAK | darmowe, offline |
| **Sentry** | monitoring błędów | zalecane | free tier |
| **Google Cloud TTS / Azure TTS** | lepsza wymowa (nagrania jakościowe) | późniejszy release | płatne per znak |
| **Słownik zewnętrzny** (np. Wiktionary dump / API) | opcjonalny cross-check halucynacji | opcjonalnie później | |
| **FCM (Firebase Cloud Messaging)** | push smart-przypomnienia | późniejszy release | darmowe |
| **Object storage (S3/R2)** | pliki audio z cloud TTS | gdy cloud TTS | tani |

> **Czy AI musi działać cały czas na backendzie?**
> Tak — funkcja „dodaj słowo” **wymaga żywego LLM API** (backend woła zewnętrznego providera przy każdym *nowym, nie-scache’owanym* słowie). Ale:
> - używamy **agresywnego cache** (Redis + tabela `lexical_cache` w Postgres) — te same słowa nie płacą drugi raz,
> - **dwuetapowo**: tani/szybki model do listy kandydatów, mocniejszy do pełnego enrichmentu (dopiero po ＋),
> - LLM potrzebny tylko do *dodawania*; **nauka/powtórki działają bez AI** (i offline).
> - Nie utrzymujemy własnego modelu — korzystamy z API providera (mniej ryzyka, szybciej).

---

## 4. Model danych — schemat docelowy (PostgreSQL)

Konwencja: `snake_case`, klucze `uuid` (gen w app lub `gen_random_uuid()`), `created_at/updated_at timestamptz`. JSONB dla treści AI (elastyczność), z wydzieleniem pól do zapytań.

```sql
-- === Użytkownicy i konfiguracja ===
users (
  id uuid pk,
  email text unique not null,
  password_hash text null,          -- null gdy tylko Google
  google_id text unique null,
  role text not null default 'user',-- 'user' | 'teacher'
  ui_lang text not null default 'pl',
  created_at timestamptz, updated_at timestamptz
)

language_profiles (              -- pary językowe usera (może mieć wiele)
  id uuid pk,
  user_id uuid fk -> users,
  native_lang text not null,       -- ISO 639-1, np. 'pl'
  learning_lang text not null,     -- np. 'es'
  cefr_level text not null default 'A2', -- A1..C1
  selected_tenses jsonb not null default '[]', -- czasy do odmiany
  last_used_at timestamptz,
  is_active boolean not null default false,  -- ostatnio używana
  unique (user_id, native_lang, learning_lang)
)

user_settings (
  user_id uuid pk fk -> users,
  practice_input_pref text default 'choice', -- choice|type|flashcard|speak
  practice_direction text default 'l2_to_l1', -- l2_to_l1|l1_to_l2|random
  typing_tolerance text default 'tolerate',  -- strict|tolerate
  typo_modal_enabled boolean default true,
  new_cards_per_day int default 20,
  theme text default 'system',
  show_usages boolean default true,              -- modal usages na rewersie fiszki
  show_synonyms_antonyms boolean default true,
  show_periphrases boolean default true,
  conjugation_expanded_default boolean default false
)

-- === Wspólna baza leksykalna (globalna, rośnie z seedem + AI) ===
lexical_entries (
  id uuid pk,
  lang_pair text not null,            -- 'pl>es'
  lemma_l2 text not null,
  lemma_l1_primary text,              -- główny gloss L1 (do wyszukiwania odwrotnego)
  pos text,
  cefr text,                          -- A1..C1 (orientacyjny)
  content jsonb not null,             -- pełna karta (patrz 5.3)
  source text not null,               -- seed|ai|curated
  created_by_user_id uuid fk -> users null, -- kto „wniósł” wpis AI (audit)
  usage_count int not null default 0, -- ile razy dodane do nauki
  created_at timestamptz, updated_at timestamptz,
  unique (lang_pair, lemma_l2, pos)
)

lexical_categories (
  id uuid pk,
  slug text unique not null,          -- colors|numbers|connectors|...
  name_i18n jsonb not null            -- {"pl":"Kolory","en":"Colors",...}
)

lexical_entry_categories (
  entry_id uuid fk -> lexical_entries,
  category_id uuid fk -> lexical_categories,
  primary key (entry_id, category_id)
)

starter_packs (
  id uuid pk,
  slug text unique not null,          -- pl-es-a1-colors
  lang_pair text not null,
  cefr_level text not null,           -- A1..C1
  category_slug text not null,
  title_i18n jsonb not null,
  description_i18n jsonb,
  sort_order int default 0,
  is_published boolean default true,
  created_at timestamptz
)

starter_pack_items (
  pack_id uuid fk -> starter_packs,
  lexical_entry_id uuid fk -> lexical_entries,
  sort_order int default 0,
  primary key (pack_id, lexical_entry_id)
)

-- === Cache szybkich lookupów (input → kandydaci) ===
lexical_cache (
  id uuid pk,
  lang_pair text not null,          -- 'pl>es'
  input_norm text not null,         -- znormalizowane słowo wejściowe
  kind text not null,               -- 'lookup' | 'enrichment'
  cefr text null,                   -- dla enrichment
  tenses_hash text null,            -- hash wybranych czasów
  payload jsonb not null,           -- wynik (structured)
  model text null,                  -- null gdy z DB/seed
  created_at timestamptz,
  unique (lang_pair, input_norm, kind, cefr, tenses_hash)
)

-- === Talie / pakiety ===
decks (
  id uuid pk,
  owner_user_id uuid fk -> users,   -- właściciel (user lub teacher)
  profile_id uuid fk -> language_profiles null,
  title text not null,
  source text not null default 'personal', -- personal|starter|teacher_list|import
  independent_srs boolean not null default false, -- osobna kolejka
  created_at timestamptz
)

-- === Karty nauki ===
learning_cards (
  id uuid pk,
  user_id uuid fk -> users,
  profile_id uuid fk -> language_profiles,
  deck_id uuid fk -> decks null,    -- null = główna lista
  lexical_entry_id uuid fk -> lexical_entries null, -- link do wspólnej bazy
  lemma_l2 text not null,           -- słowo w języku nauki
  pos text,                         -- part of speech
  gloss_primary text,               -- główne znaczenie L1 (do szybkich zapytań)
  content jsonb not null,           -- pełna karta (patrz 5.3)
  is_favorite boolean default false,
  audio_ready boolean default false,
  created_at timestamptz, updated_at timestamptz,
  unique (user_id, profile_id, lemma_l2, pos, deck_id)
)

favorite_words (                  -- ♥ bez wejścia do SRS
  id uuid pk,
  user_id uuid fk -> users,
  profile_id uuid fk -> language_profiles,
  lemma text not null, pos text, gloss text,
  created_at timestamptz
)

-- === SRS ===
srs_state (
  id uuid pk,
  card_id uuid fk -> learning_cards,
  scope text not null default 'main', -- 'main' | deck_id::text (osobny pakiet)
  ease real not null default 2.5,
  interval_days real not null default 0,
  repetitions int not null default 0,
  lapses int not null default 0,
  status text not null default 'new', -- new|learning|review|suspended
  next_review_at timestamptz,
  last_reviewed_at timestamptz,
  last_grade text,                    -- hard|easy|know_well
  unique (card_id, scope)
)

review_logs (
  id uuid pk,
  card_id uuid fk -> learning_cards,
  user_id uuid fk -> users,
  grade text not null,               -- hard|easy|know_well
  mode text not null,                -- choice|type|speak
  direction text,                    -- l2_to_l1 | l1_to_l2
  correct boolean,
  reviewed_at timestamptz
)

-- === Nauczyciel (v0.3, za feature flagą) ===
classes (
  id uuid pk, teacher_user_id uuid fk -> users,
  name text, join_code text unique, created_at timestamptz
)
class_memberships (
  id uuid pk, class_id uuid fk -> classes,
  student_user_id uuid fk -> users, joined_at timestamptz,
  unique (class_id, student_user_id)
)
teacher_word_lists (
  id uuid pk, teacher_user_id uuid fk -> users,
  title text, lang_pair text, created_at timestamptz
)
teacher_list_items (
  id uuid pk, list_id uuid fk -> teacher_word_lists,
  lemma_l2 text, gloss text, pos text, note text
)
list_assignments (
  id uuid pk, list_id uuid fk -> teacher_word_lists,
  class_id uuid fk -> classes null,
  student_user_id uuid fk -> users null,
  as_independent_deck boolean default true,
  assigned_at timestamptz
)

-- === Sync offline ===
sync_cursors (
  user_id uuid pk, last_pulled_at timestamptz
)
```

Indeksy m.in.: `srs_state(next_review_at, status)`, `learning_cards(user_id, profile_id)`, `lexical_cache(unique...)`.

---

## 5. Warstwa leksykalna + AI — pipeline i kontrakty

### 5.0 Zasada: DB first, AI fallback, zapis zwrotny

```
User input
    │
    ▼
Normalize (case, trim, diakrytyki wg reguł wyszukiwania)
    │
    ▼
Szukaj w lexical_entries (+ lexical_cache)  ──hit──► kandydaci / pełna karta
    │
   miss
    │
    ▼
OpenAI lookup / enrichment
    │
    ▼
Zapisz do lexical_entries (+ cache)  ──► dostępne dla WSZYSTKICH userów
    │
    ▼
Przy ＋: utwórz prywatną learning_cards (+ srs_state)
```

- Seed (`source=seed`) wgrywany migracją / skryptem — baza nie jest pusta na starcie.
- Wpis z AI (`source=ai`) od razu staje się częścią wspólnej bazy.
- `usage_count++` gdy user dodaje wpis do nauki (metryka popularności).

### 5.1 Dwuetapowość (gdy miss w DB)

1. **Lookup (szybki):** wejście = słowo + `lang_pair` + `cefr`. Model tani/szybki.
   - Sprawdź `lexical_entries` / cache → jeśli miss, wywołaj LLM z krótkim promptem „structured output”.
   - Zwróć listę kandydatów (lemat, POS, krótki gloss); przy AI — zapisz lookup do cache.
2. **Enrichment (pełny):** wywoływany przy **＋** (lub w tle przez workera).
   - Najpierw pełny wpis z `lexical_entries` jeśli już jest.
   - Inaczej: model mocniejszy, structured output → zapis do `lexical_entries` + `lexical_cache`.
   - Utworzenie `learning_cards` dla usera.
   - Prefetch audio (v0.1: nic — TTS on-device).

### 5.2 Structured output i walidacja

- Używamy **JSON Schema / structured outputs** providera (function/tool calling lub response_format=json_schema).
- Po stronie backendu **walidacja Pydantic**; jeśli niezgodne → retry z naprawą lub oznaczenie karty jako „do przeglądu”.
- Prompty wersjonowane w `backend/app/ai/prompts/` (z numerem wersji w cache key, żeby zmiana promptu odświeżyła cache).

### 5.3 Schemat karty (enrichment) — JSON

```json
{
  "schema_version": "1.0",
  "lemma": "vacío",
  "language": "es",
  "pos": "adj",
  "ipa": "baˈθi.o",
  "meanings": [
    {
      "gloss_l1": "pusty",
      "synonyms_l1": ["próżny"],
      "examples": [
        {"l2": "La botella está vacía.", "l1": "Butelka jest pusta.", "cefr": "A2"},
        {"l2": "Un cuarto vacío.", "l1": "Pusty pokój.", "cefr": "A1"}
      ],
      "usages": ["estar vacío", "espacio vacío"]
    }
  ],
  "synonyms_l2": ["desocupado", "hueco"],
  "antonyms_l2": ["lleno", "pleno"],
  "conjugation": null,
  "notes": null,
  "confidence": 0.94
}
```

Dla czasownika `conjugation` np.:

```json
"conjugation": {
  "tenses": {
    "presente": {"yo":"hablo","tú":"hablas","él":"habla", "...":"..."},
    "preterito_indefinido": {"...":"..."}
  }
}
```

### 5.4 Reguły akceptacji odpowiedzi (tryb „Wpisz”)

- Poprawne zależą od **kierunku** (`practice_direction` / wylosowany kierunek sesji):
  - **L2→L1:** `gloss_l1` lub `synonyms_l1` z karty.
  - **L1→L2:** `lemma` (L2) lub `synonyms_l2` z karty.
- Normalizacja: trim, lower-case, redukcja wielokrotnych spacji.
- Tryb `tolerate`: dopuszczalny 1-znakowy dystans Levenshteina lub brak znaków diakrytycznych → uznaj, pokaż modal korekty (jeśli włączony).
- Tryb `strict`: tylko po normalizacji case/spacji.
- Logika czysta (bez AI w czasie odpowiedzi) → szybka i offline-friendly.

### 5.5 Seed packs — odłożone

Schemat tabel (`starter_packs`, kategorie) zostaje w modelu na później.  
**Pierwszy priorytet implementacji:** pipeline tworzenia pełnej, bogatej karty (wpisz → DB/AI → uporządkowany JSON → UI karty).  
Curated seed (PL↔ES, CEFR × kategorie) wgrywamy dopiero po akceptacji jakości kart.

### 5.6 Koszty i limity

- DB hit = $0; AI tylko przy miss.
- Cache + rate limit per user (np. X lookupów AI/min) — ochrona kosztów i abuse.
- Metryki: cache/DB hit ratio, liczba wywołań LLM, koszt/dzień.
---

## 6. Silnik SRS

### 6.1 Algorytm

Wariant **SM-2 uproszczony** z 3 ocenami:

| Ocena | grade | Efekt |
|-------|-------|-------|
| Trudne | hard | interval × ~1.2, ease − 0.15 (min 1.3), powtórka wkrótce |
| Łatwe | easy | interval × ease |
| Znam dobrze | know_well | interval × ease × ~1.3, ease + 0.05 |

- Nowa karta: kilka kroków „learning” (np. 1 min / 10 min / 1 dzień) zanim wejdzie w `review`.
- `next_review_at = now + interval_days`.
- Błędna odpowiedź (w trybie choice/type) → traktowana jak „hard” + `lapses++` (opcjonalnie reset do learning).

Algorytm w czystym module `services/srs.py` (bez zależności od web) → **te same reguły portujemy do Androida (Kotlin)** dla trybu offline; serwer jest źródłem prawdy przy sync (last-write-wins po `reviewed_at`, albo merge po logach).

### 6.2 Kolejkowanie sesji „Ćwicz”

1. Karty **due** (`next_review_at <= now`, status review/learning), posortowane rosnąco po `next_review_at`.
2. Potem **nowe** (status new) do wyczerpania `new_cards_per_day`.
3. Zakres: główna lista lub konkretny pakiet (`scope`).
4. Powtórki due — bez limitu.

---

## 7. API — kontrakt (skrót)

Auth: Bearer JWT (access + refresh). Wszystkie odpowiedzi JSON, wersjonowanie `/api/v1`.

```
POST /api/v1/auth/register            {email, password} -> tokens
POST /api/v1/auth/login               {email, password} -> tokens
POST /api/v1/auth/google              {id_token} -> tokens
POST /api/v1/auth/refresh             {refresh} -> tokens

GET  /api/v1/me
GET/PUT /api/v1/me/settings
GET/POST /api/v1/profiles             # pary językowe
PUT  /api/v1/profiles/{id}/activate   # ustaw ostatnio używaną

POST /api/v1/lookup                   {text, profile_id} -> {candidates[], source: db|ai}
POST /api/v1/cards                    {lemma, pos, profile_id, deck_id?} -> card (enrichment; DB first)
GET  /api/v1/cards?profile_id=&deck_id=
POST /api/v1/favorites                {lemma, pos, gloss, profile_id}
GET  /api/v1/favorites

GET  /api/v1/packs?profile_id=        -> starter packs (CEFR + kategorie)
GET  /api/v1/packs/{id}               -> items
POST /api/v1/packs/{id}/add           {mode: all|selected, entry_ids?, as_independent_deck?}

GET  /api/v1/srs/queue?profile_id=&deck_id=  -> {due[], new[]}
POST /api/v1/srs/review               {card_id, grade, mode, direction, correct}

GET  /api/v1/sync/pull?since=         -> {cards[], srs[], settings}
POST /api/v1/sync/push                {reviews[], settings?}

# v0.3 teacher (feature flag)
POST /api/v1/teacher/classes
POST /api/v1/teacher/lists
POST /api/v1/teacher/lists/{id}/assign
GET  /api/v1/teacher/students/{id}/progress
POST /api/v1/classes/join             {join_code}
```

OpenAPI generowane automatycznie przez FastAPI → używane do generacji klienta/testów.

---

## 8. Fazy implementacji

Każda faza kończy się: działający wycinek + testy + zielone CI + krótka notka w changelogu.

### Faza 0 — Fundament (repo, CI, szkielety)
- Monorepo, `docker-compose` (Postgres + Redis), pre-commit (ruff/black/mypy).
- FastAPI „hello” + healthcheck; Android projekt startowy (Compose, Hilt, nawigacja).
- GitHub Actions: lint + testy dla backend i android.
- **DoD:** `docker-compose up` stawia backend+DB; apka się kompiluje i uruchamia pusty ekran.

### Faza 1 — Auth + profile + ustawienia
- Modele users/profiles/settings + migracje.
- Rejestracja/login (email+hasło, JWT refresh), Google id_token.
- Android: ekrany rejestracji/logowania, przechowywanie tokenów (EncryptedSharedPrefs/DataStore), onboarding L1/L2/CEFR/czasy, zapamiętanie aktywnej pary.
- **DoD:** można założyć konto, zalogować, przejść onboarding, wznowić apkę w ostatniej konfiguracji.

### Faza 2 — Wspólna baza + AI lookup + bogata karta + ♥/＋  ★ CORE
- Tabele `lexical_entries` (+ kategorie w schemacie, bez seedu treści).
- Lookup: **DB first → OpenAI fallback → zapis do wspólnej bazy**.
- **Priorytet:** jakość enrichmentu — pełna, uporządkowana karta (znaczenia, przykłady, syn/ant, użycia, odmiana…).
- Iteracja promptów + walidacja JSON + UI karty, aż flow „wpisz słowo → OK → super karta” będzie satysfakcjonujący.
- Endpoint `/lookup`, `/cards`; Android: „Dodaj słowo”, lista ♥/＋, ekran karty.
- Starter packs / seed — **celowo pominięte** w tej fazie.
- **DoD:** wpisuję słowo → pełna, czytelna karta w < ~kilka s; drugi raz to samo słowo idzie z DB bez AI.

### Faza 3 — SRS + sesja „Ćwicz”
- `services/srs.py` + endpointy queue/review; log powtórek.
- Tryby: wybór 8 opcji + wpisywanie + **fiszki** (przód → rewers); **kierunek karty** `l2_to_l1` / `l1_to_l2` / `random`.
- Rewers fiszki: znaczenia + usages modal + syn/ant ♥/＋ + peryfrazy + odmiana collapsible (`selected_tenses`, `conjugation_expanded_default`).
- Flagi: `show_usages`, `show_synonyms_antonyms`, `show_periphrases`.
- Android: ekran sesji, oceny trudne/łatwe/znam dobrze, modale feedbacku, ustawienie kierunku i formy.
- **DoD:** pełny cykl: słowo → ćwicz w obu kierunkach → SRS planuje powtórkę.

### Faza 3b — Starter packs / seed (po akceptacji jakości kart)
- Seed PL↔ES (CEFR × kategorie) + API `/packs` + UI list.
- **DoD:** pakiety widoczne; dodanie do nauki bez AI.

### Faza 4 — Offline + sync
- Room: encje card/srs/settings; repo z „single source of truth” (network + cache).
- WorkManager: sync push/pull, kolejka powtórek offline.
- Port algorytmu SRS do Kotlina; strategia rozwiązywania konfliktów.
- **DoD:** samolotowy: powtórki działają offline, po sieci stan się synchronizuje bez utraty danych.

### Faza 5 — Hardening v0.1 (stabilność)
- Rate limiting AI, obsługa błędów LLM (timeout/fallback), retry z backoff.
- Pełne testy e2e głównych flow; testy obciążeniowe lookup (cache).
- Sentry, structured logs, healthchecks, metryki kosztu AI.
- Dostępność (TalkBack), i18n (PL, EN, ES, DE, FR, IT, PT, UK), ciemny motyw.
- **DoD:** brak znanych krytycznych błędów; happy path i błędy sieci obsłużone; release candidate v0.1.

### Faza 6 (v0.2) — Speech + polish
- Tryb „powiedz” (SpeechRecognizer), lepsza tolerancja literówek, cache/UX tuning.

### Faza 7 (v0.3) — Teacher
- Panel web (Next.js), klasy/kody/listy/przypisania, podgląd postępów (trudne/łatwe/znam dobrze), pakiety z osobnym SRS.

### Faza 8 (v0.4+) — Conjugación drills, cloud TTS, smart przypomnienia, iOS/web
- Ćwiczenia odmiany czasowników (uzupełnianie formy w zdaniu, trening czasu).
- Cloud TTS + storage audio, FCM push z treścią.

---

## 9. Testowanie i jakość

| Warstwa | Testy |
|---------|-------|
| Backend unit | services (SRS, akceptacja odpowiedzi, generator dystraktorów, normalizacja) |
| Backend integration | endpointy + Postgres (testcontainers), mock LLM |
| Kontrakt AI | walidacja schematu na „złotych” próbkach + test na złośliwe/niepełne odpowiedzi LLM |
| Android unit | ViewModele, repo, mapowania, port SRS |
| Android UI | Compose testy kluczowych ekranów |
| E2E | scenariusz: register → add → practice → sync (MockWebServer / staging) |
| Non-func | rate limit, load na lookup z cache, offline/online przełączanie |

CI (GitHub Actions): lint+typy → testy backend (z usługami) → build+test Android → (deploy na staging przy merge do main).

---

## 10. Bezpieczeństwo i prywatność

- Hasła: bcrypt; JWT krótkie access + rotowane refresh; wylogowanie/rewokacja.
- HTTPS wszędzie; CORS ograniczony do znanych klientów (web panel).
- Rate limiting + walidacja wejść (Pydantic) → ochrona przed abuse i wstrzyknięciami do promptu.
- Sekrety wyłącznie w env/secret store; nic w repo.
- Dane usera (słówka) — eksport/usunięcie konta (RODO-friendly) zaplanowane.
- LLM: nie wysyłamy danych wrażliwych; logujemy minimalnie.

---

## 11. Wątpliwości techniczne do rozstrzygnięcia

1. **Provider LLM:** OpenAI (GPT-4o-mini/4o) vs Anthropic (Haiku/Sonnet)?  
   **Propozycja:** abstrakcja providera + start na tanim modelu do lookup i średnim do enrichment; wybór ostateczny po teście jakości ES↔PL.
2. **Worker do enrichmentu:** synchronicznie w request (prościej) czy async przez arq (szybszy UX, skalowalne)?  
   **Propozycja:** v0.1 synchronicznie z timeoutem + skeleton; async przełączymy, gdy enrichment będzie cięższy (audio/conjugación).
3. **Sync offline — konflikty:** last-write-wins po `reviewed_at` czy merge po `review_logs`?  
   **Propozycja:** replay `review_logs` na serwerze (idempotentnie) = najbezpieczniejsze.
4. **Hosting:** Railway (najszybciej) vs Fly.io (bliżej użytkowników/regiony)?  
   **Propozycja:** Railway na start, migracja jeśli trzeba.
5. **Jakość TTS systemowego dla ES:** zależna od urządzenia; jeśli słabo → wcześniejsze wejście cloud TTS dla ES.
6. **Diakrytyki w „strict”:** czy brak `ñ/ó` w trybie strict to błąd? (proponuję: w strict — tak; w tolerate — akceptowane z modalem).
7. **Wersjonowanie promptów vs cache:** klucz cache zawiera wersję promptu (zmiana promptu = świeże dane) — potwierdzić.
8. **Multi-region danych / RODO:** gdzie trzymamy DB (UE)?  
   **Propozycja:** region UE.

---

## 12. Definicja „gotowej, działającej aplikacji” (v0.1)

- User rejestruje się (email/Google), wybiera języki, poziom, czasy, **kierunek karty**.
- W bazie są **starter packs** (CEFR × kategorie); można dodać pakiet do nauki bez AI.
- Dodaje słowo: **najpierw wspólna DB**, przy miss OpenAI; wynik **zapisany globalnie**; lista < ~2 s; ＋ buduje pełną kartę; play działa.
- Ćwiczy: kolejka due→new, tryby wybór/wpisz/**fiszki**, **przód L2 lub L1**, oceny 3-stopniowe, SRS.
- Działa offline dla już dodanych kart; sync bezstratny.
- Stabilne: obsługa błędów sieci/LLM, brak crashy w happy path, testy zielone.

---

*Dokument techniczny — do aktualizacji wraz z decyzjami z sekcji 11. Ostatnia aktualizacja: shared lexical DB, seed packs, practice_direction.*
