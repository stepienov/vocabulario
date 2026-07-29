# Checklista startowa — co musisz dostarczyć / załatwić / wybrać

Ten dokument to praktyczna lista rzeczy, które musisz ogarnąć, żebym mógł zbudować aplikację od zera aż do publikacji w **Google Play**, z działającym **CI/CD na Railway**.

Legenda priorytetu:
- 🔴 **Blokuje** — bez tego nie ruszymy z daną częścią.
- 🟡 **Potrzebne przed publikacją** — mogę pisać kod, ale do release trzeba mieć.
- 🟢 **Opcjonalne / później** — miło mieć, nie blokuje v0.1.

Legenda „kto”:
- **[TY]** — musisz założyć/kupić/zdecydować (wymaga Twojego konta, karty, danych osobowych).
- **[JA]** — zrobię w kodzie/konfiguracji, gdy dostanę materiały.

---

## 1. Decyzje do potwierdzenia (szybkie — odpisz jednym słowem)

Z sekcji „wątpliwości technicznych”. Jeśli nic nie napiszesz, idę z **propozycją**.

| # | Decyzja | Propozycja | Twój wybór |
|---|---------|-----------|-----------|
| 1 | Provider AI | **OpenAI** (start), abstrakcja pozwala zmienić | ✅ klucz w `.env` |
| 2 | Enrichment sync/async | **sync + skeleton** na v0.1 | |
| 3 | Sync offline | **replay review_logs** | |
| 4 | Hosting (później) | **Railway** | nie blokuje lokalnego startu |
| 5 | Region bazy danych | **UE** (RODO) | |
| 6 | Diakrytyki w trybie „ściśle” | brak ñ/ó = błąd (w „toleruj” akceptowane) | |
| 7 | Nazwa aplikacji + `applicationId` | do ustalenia (placeholder OK lokalnie) | |
| 8 | Auth v0.1 | **email + Google od razu** | ✅ |
| 9 | Wspólna baza | **najpierw szukaj w DB, potem AI, zapis z powrotem** | ✅ |
| 10 | Kierunek karty | przód w języku uczonym / ojczystym / losowo | ✅ |
| 11 | Gotowe zestawy słówek (seed) | **później** — najpierw jakość tworzenia kart | ✅ |
| 12 | Nazwa / identyfikator pakietu | tymczasowo Vocabulario / placeholder | ✅ |

> `applicationId` (package name) jest **na zawsze** przypisany do aplikacji w Google Play — nie da się go później zmienić. Warto wybrać świadomie (np. własna domena odwrócona).

---

## 1b. Gotowość lokalna (stan maszyny — sprawdzone)

| Element | Status | Uwagi |
|---------|--------|-------|
| Python 3.12 | ✅ | 3.12.0 |
| pip | ✅ | |
| Docker Desktop + Compose | ✅ | daemon działa |
| `.env` + `OPENAI_API_KEY` | ✅ | lokalnie; **nie commitować** |
| Android Studio | ✅ | zainstalowane |
| Android SDK | ✅ | `%LOCALAPPDATA%\Android\Sdk` |
| Emulatory AVD | ✅ | `Galaxy_S24`, `Medium_Phone` |
| JDK 17 / 21 | ✅ | Studio ma własne JBR; masz też jdk-17 i jdk-21 |
| `ANDROID_HOME` / `adb` w PATH | ⚠️ | nie w PATH — **OK z Android Studio**; CLI opcjonalnie |
| Java w PATH = 1.8 | ⚠️ | nie szkodzi Studio; do Gradle CLI ustaw `JAVA_HOME` na jdk-17/21 |
| Railway / Google Play | ⏭ | niepotrzebne do lokalnego v0.1 |

**Emulator:** po zbudowaniu apki w Android Studio → Device Manager → `Galaxy_S24` lub `Medium_Phone` → Run. Emulator → backend hosta: `http://10.0.2.2:8000` (już w `ALLOWED_ORIGINS`).

**Opcjonalnie (wygodniejszy terminal)** — dodaj do PATH użytkownika:
- `%LOCALAPPDATA%\Android\Sdk\platform-tools`
- `%LOCALAPPDATA%\Android\Sdk\emulator`
- `ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk`
- `JAVA_HOME=C:\Program Files\Java\jdk-17`

---

## 2. Konta i klucze — AI (🔴 kluczowe dla „dodaj słowo”)

| Co | Kto | Priorytet | Uwagi |
|----|-----|-----------|-------|
| Konto **OpenAI** z billingiem | [TY] | 🔴 | ✅ masz; trzymaj limit wydatków |
| **API key** LLM | [TY] | 🔴 | ✅ w lokalnym `.env`; później też Railway secrets |
| Wybór modeli (lookup/enrichment) | [JA] proponuję, [TY] akceptujesz | 🟡 | start: `gpt-4o-mini` |

Bez klucza AI zbuduję wszystko poza realnym generowaniem kart (użyję mocka do testów), ale do działającej apki klucz jest wymagany.

---

## 3. Logowanie Google (🔴 — chcesz od razu w pierwszej wersji)

Potrzebuję od Ciebie z **Google Cloud** (konto Google wystarczy; to darmowe):

1. Wejdź na [Google Cloud Console](https://console.cloud.google.com/).
2. Utwórz **nowy projekt** (np. nazwa: Vocabulario).
3. Włącz ekran zgody OAuth (Consent screen): typ **External**, nazwa apki tymczasowo „Vocabulario”, Twój email jako kontakt.
4. Utwórz **dwa** identyfikatory klienta OAuth:
   - typ **Web** — dla backendu (weryfikacja tokenu),
   - typ **Android** — dla apki (tu później podamy odcisk SHA-1 z debug keystore; na początku mogę Ci powiedzieć dokładnie gdzie kliknąć i co wkleić).
5. Skopiuj mi (albo wklej do `.env`):
   - identyfikator klienta typu **Web** → `GOOGLE_OAUTH_CLIENT_ID`
   - identyfikator klienta typu **Android** → `GOOGLE_OAUTH_CLIENT_ID_ANDROID`

Na razie **nie musisz** nic płacić ani publikować apki w Google.  
Jeśli wolisz, mogę Ci zrobić osobną, klik-po-kliku instrukcję ze zrzutami ścieżek w konsoli — napisz tylko „daj instrukcję Google krok po kroku”.

| Co | Kto | Priorytet |
|----|-----|-----------|
| Projekt w Google Cloud | [TY] | 🔴 |
| Ekran zgody OAuth | [TY] | 🔴 |
| Klient OAuth „Web” + „Android” | [TY] wg mojej instrukcji | 🔴 |
| SHA-1 podpisu debug | [JA] wygeneruję / podam Ci komendę | 🔴 |

---

## 4. Hosting / infrastruktura — Railway (🔴)

Masz już Railway (płatny) — super. Potrzebne:

| Co | Kto | Priorytet | Uwagi |
|----|-----|-----------|-------|
| Nowy **projekt/serwis** dla vocabulario (lub w istniejącym) | [TY] zapraszasz mnie / dajesz dostęp albo wklejasz zmienne | 🔴 | trzymajmy osobno od Twojej obecnej apki |
| **PostgreSQL** plugin na Railway | [TY] klik „add Postgres” | 🔴 | region UE jeśli dostępny |
| **Redis** plugin na Railway | [TY] klik „add Redis” | 🔴 | cache + kolejki |
| **Zmienne środowiskowe** (sekrety) w Railway | [TY] wklejasz wartości, [JA] mówię jakie klucze | 🔴 | patrz sekcja 8 |
| Token/dostęp do wdrożeń (Railway token do CI) | [TY] | 🟡 | do auto-deploy z GitHub Actions |

Jak dać mi dostęp: albo dodajesz mnie jako collaboratora w Railway, albo Ty klikasz wg moich instrukcji, a ja przygotowuję `Dockerfile` + `railway.json`/konfigurację tak, żeby deploy „sam się robił” po merge do `main`.

---

## 5. GitHub / CI-CD (🟡 — w większości [JA])

| Co | Kto | Priorytet | Uwagi |
|----|-----|-----------|-------|
| Repo `vocabulario` (już jest) | ✅ | | |
| GitHub Actions workflows (lint, testy, build) | [JA] | 🟡 | |
| **GitHub Secrets**: `RAILWAY_TOKEN`, klucze do buildu Androida | [TY] wklejasz | 🟡 | ja podam nazwy |
| Auto-deploy backend na Railway po merge | [JA] konfiguruję | 🟡 | |
| Build APK/AAB + (opcjonalnie) auto-upload do Play | [JA] konfiguruję | 🟢 | wymaga service account Google Play |

---

## 6. Google Play — publikacja aplikacji (🔴 dla wejścia do sklepu)

To najwięcej „papierologii” po Twojej stronie. Bez tego apka może działać, ale nie wejdzie do sklepu.

| Co | Kto | Priorytet | Uwagi |
|----|-----|-----------|-------|
| **Konto Google Play Developer** (jednorazowo **~25 USD**) | [TY] | 🔴 | rejestracja + weryfikacja tożsamości |
| Weryfikacja tożsamości / dane (od 2023 Google wymaga; konto osobiste lub firmowe/D-U-N-S) | [TY] | 🔴 | może potrwać — zacznij wcześnie |
| **Nazwa aplikacji** w sklepie | [TY] | 🟡 | |
| **Ikona** (512×512), **feature graphic** (1024×500) | [TY] lub [JA generuję wstępne] | 🟡 | mogę wygenerować placeholdery |
| **Zrzuty ekranu** (min. kilka, telefon) | [JA] z gotowej apki | 🟡 | |
| **Opis krótki + pełny** (PL/EN) | [JA] draft, [TY] akceptujesz | 🟡 | |
| **Polityka prywatności** (URL, wymagana) | [JA] draft + [TY] hostujesz/potwierdzasz | 🔴 | wymóg Google |
| **Data safety form** (co zbieramy: email, słówka) | [JA] przygotuję treść, [TY] wypełniasz w konsoli | 🔴 | |
| Kategoria (Education), treści, wiek | [TY] w konsoli | 🟡 | |
| **Klucz podpisywania aplikacji** (App Signing) | [JA] generuję upload key, [TY] włączasz Play App Signing | 🔴 | trzymamy keystore w sekretach |
| Konto testerów (internal testing track) | [TY] podajesz maile | 🟢 | szybka ścieżka do testów |
| (Opcjonalnie) **Service Account** do auto-uploadu buildów | [TY] w Play Console + GCP | 🟢 | pełne CI/CD do sklepu |

**Najszybsza ścieżka do „jest w sklepie”:**
1. Zakładasz konto developer (25 USD) + weryfikacja — **zrób to od razu**, bo weryfikacja bywa wąskim gardłem.
2. Ja buduję apkę do stanu „internal testing”.
3. Wrzucamy na **Internal testing** (dostępne w minuty, wąskie grono) → potem **Closed/Open testing** → **Production**.

---

## 7. TTS / audio (🟢 v0.1 za darmo)

| Co | Kto | Priorytet | Uwagi |
|----|-----|-----------|-------|
| Systemowy TTS Androida | [JA] | 🟢 | działa od razu, za darmo |
| (Później) Cloud TTS (Google/Azure) + storage | [TY] konto/billing, [JA] integracja | 🟢 | tylko jeśli systemowy będzie za słaby dla ES |

---

## 8. Sekrety — lista zmiennych, które wypełnisz (🔴)

Ja przygotuję `.env.example`; Ty wklejasz wartości w Railway (backend) i GitHub Secrets (CI). Wstępny zestaw:

```
# Backend / Railway
DATABASE_URL=...            # z pluginu Postgres (Railway wstawi)
REDIS_URL=...               # z pluginu Redis (Railway wstawi)
JWT_SECRET=...              # [JA generuję losowo]
OPENAI_API_KEY=...          # [TY]
LLM_PROVIDER=openai         # openai|anthropic
GOOGLE_OAUTH_CLIENT_ID=...  # [TY] (jeśli logowanie Google)
SENTRY_DSN=...              # [TY] opcjonalnie
ENVIRONMENT=production
ALLOWED_ORIGINS=...         # panel web później

# GitHub Actions (CI/CD)
RAILWAY_TOKEN=...           # [TY]
ANDROID_KEYSTORE_BASE64=... # [JA generuję, TY przechowujesz]
ANDROID_KEYSTORE_PASSWORD=...
ANDROID_KEY_ALIAS=...
ANDROID_KEY_PASSWORD=...
PLAY_SERVICE_ACCOUNT_JSON=... # opcjonalnie, do auto-upload
```

---

## 9. Monitoring (🟢 zalecane)

| Co | Kto | Priorytet |
|----|-----|-----------|
| Konto **Sentry** (free tier) + DSN | [TY] | 🟢 |
| Integracja Sentry backend + Android | [JA] | 🟢 |

---

## 10. Co robię JA bez czekania na Ciebie

Mogę od razu zacząć i dowieźć duży kawał, używając mocków/lokalnych usług:

- szkielet repo (backend + Android), docker-compose (Postgres+Redis lokalnie),
- schemat bazy + migracje, auth email+hasło, profile, ustawienia,
- lookup/enrichment za **mockiem AI** (podmienimy na realny klucz jednym ustawieniem),
- SRS + sesja Ćwicz, Room + offline sync,
- CI (lint+testy+build), `Dockerfile`, konfiguracja deploy pod Railway,
- drafty: polityka prywatności, opis do sklepu, treść „Data safety”,
- wstępne ikony/placeholdery graficzne.

Realne działanie „end-to-end w chmurze + w sklepie” odblokują Twoje rzeczy z sekcji 2, 4 i 6.

---

## 11. Twoja lista TODO — priorytetowo (skrót)

**Zrób najpierw (odblokowuje najwięcej):**
1. 🔴 Załóż **konto Google Play Developer** (25 USD) i zacznij weryfikację tożsamości — to najdłużej trwa.
2. 🔴 Załóż **klucz OpenAI** + ustaw limit wydatków; przekaż mi (przez Railway secret).
3. 🔴 Na **Railway**: nowy serwis + dodaj **Postgres** i **Redis**; daj mi dostęp lub przygotuj się do wklejania zmiennych.
4. 🟡 Zdecyduj: v0.1 z Google Login czy tylko email? (jeśli Google — projekt w Google Cloud + OAuth client).
5. 🟡 Wybierz **nazwę aplikacji** i **applicationId** (package).

**Przed publikacją:**
6. 🔴 Polityka prywatności (URL) + Data safety (wypełnisz treścią ode mnie).
7. 🟡 Ikona/materiały graficzne (mogę wygenerować, Ty akceptujesz).
8. 🟢 Konto Sentry, service account do auto-uploadu (jeśli chcesz pełne CI/CD do sklepu).

---

## 12. Lokalne „Definition of Done” (zanim wrócimy do Railway/Play)

Po implementacji lokalnej (pierwszy etap) będzie można:

1. `docker compose up` → Postgres + Redis (+ backend).  
2. Android Studio → emulator → rejestracja email **lub Google** → onboarding.  
3. Wpisanie słowa → pełna, uporządkowana karta (to dopracowujemy w pierwszej kolejności).  
4. Drugie wyszukanie tego samego słowa idzie z naszej bazy, bez ponownego płacenia AI.  
5. Potem: ćwiczenia, offline, a **gotowe zestawy słówek** dopiero gdy karty będą OK.

---

*Do startu kodu: Google Cloud (projekt + dwa klienty OAuth) — mogę dać instrukcję krok po kroku. Reszta decyzji domknięta.*
