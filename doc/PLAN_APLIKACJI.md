# Vocabulario — plan aplikacji do nauki słówek

Dokument roboczy do wspólnego planowania. Będziemy go uzupełniać i doprecyzowywać.

---

## 1. Wizja produktu

**Vocabulario** to prosta aplikacja Android do nauki języka (MVP: **polski ↔ hiszpański**), która łączy:

- **błyskawiczne dodawanie słówek** (wpisz → AI przygotuje kartę w ~2 s),
- **bogatą, ale czytelną kartę słowa** (znaczenia, synonimy, antonimy, przykłady, odmiana, użycia),
- **uproszczony SRS** (jak Anki, ale bez ręcznego „klepania” fiszek),
- **wymowę** (przycisk play przy hiszpańskich słowach i zdaniach).

Cel UX: otworzyć → dodać lub ćwiczyć → wrócić do nauki języka. Zero mozolnego przygotowywania materiałów.

---

## 2. Problem, który rozwiązujemy

Klasyczne fiszki (Anki itd.):

- wymagają ręcznego tworzenia kart,
- często są „suche” (słowo → tłumaczenie),
- kontekst, odmiana i użycia trzeba dokładać samemu.

Chcemy odwrotności: **user podaje impuls** („pusty”), **AI + backend budują kompletną kartę**, user tylko zatwierdza (serduszko / plus).

---

## 3. Persona i założenia językowe

| Założenie | Opis |
|-----------|------|
| Język ojczysty (L1) | polski |
| Język docelowy (L2) | hiszpański |
| Kierunek | dwukierunkowe wyszukiwanie (PL→ES oraz ES→PL) |
| Poziom | ustawiany przez usera (np. A1–C1) — wpływa na przykładowe zdania |
| Platforma MVP | Android |
| UI | wizualnie miły, maksymalnie prosty, bez przeładowania |

W przyszłości: para języków konfigurowalna (L1/L2 w ustawieniach).

---

## 4. Główne flow aplikacji

### 4.1 Ekran startowy (Home)

Dwa duże przyciski:

1. **Dodaj słowo**
2. **Ćwicz**

Plus dyskretny dostęp do: ulubione, obecnie uczone, ustawienia, profil.

### 4.2 Rejestracja / logowanie

Najprostsza autoryzacja na start:

- email + hasło **lub** magic link / OTP,
- ewentualnie Google Sign-In (Android-friendly).

MVP rekomendacja: **email + hasło** (JWT) — szybkie do wdrożenia, wystarczające do synchronizacji z Postgres.

### 4.3 Dodaj słowo — wyszukiwanie

1. User wybiera (lub ma zapisane): **mój język** (PL) i **język nauki** (ES).
2. Wpisuje słowo (bez konieczności ręcznego wyboru kierunku — system wykrywa / proponuje).
3. Po zatwierdzeniu backend + agent AI zwracają wyniki.

#### Gdy wpisano słowo **polskie** (np. „pusty”)

- lista **1+ hiszpańskich odpowiedników** (np. *vacío*, *vacante*, *hueco*…),
- przy każdym:
  - **♥** — dodaj do ulubionych,
  - **＋** — dodaj do *obecnie uczonych* (tworzy rekord nauki / kartę SRS).

#### Gdy wpisano słowo **hiszpańskie** (np. „vacío”)

- jedno (lub kilka wariantów tego samego lematu) słowo hiszpańskie,
- poniżej: znaczenia po polsku,
- te same przyciski **♥** / **＋**.

### 4.4 Karta słowa (po dodaniu „＋”)

Rekord w DB zawiera m.in.:

| Pole | Opis |
|------|------|
| Słowo ES | forma bazowa (lemat) |
| Synonimy | lista ES |
| Antonimy | lista ES (rzeczowniki, przymiotniki, inne — gdy ma sens) |
| Znaczenia PL | wszystkie występujące znaczenia osobno |
| Zdanie przykładowe | **per znaczenie**, na poziomie nauki usera |
| Tłumaczenie zdania | PL |
| Oboczność / warianty | formy pokrewne, regionalizmy jeśli istotne |
| Najczęstsze użycia | charakterystyczne kolokacje / wypowiedzi |
| Odmiana (conjugación) | czasy zaznaczone przez usera w ustawieniach |
| Część mowy | verb / noun / adj / … |
| Audio | TTS lub nagrania — play przy ES słowach i zdaniach |

Idea: ucząc się **jednego** słowa, budujesz **kompleksową, ale indywidualną** kartę — kontekst, nie tylko tłumaczenie.

### 4.5 Nauka (Ćwicz) + SRS

- Do sesji trafiają słowa oznaczone **＋** (obecnie uczone).
- Uproszczony SRS (np. SM-2 uproszczony lub wariant Anki-like):
  - interwały: np. ponów / trudne / ok / łatwe,
  - `next_review_at`, `ease`, `interval`, `repetitions`.
- Tryby ćwiczeń (MVP → później):
  1. **MVP:** ES → PL (pokazujesz słowo/zdanie ES, odsłaniasz znaczenie),
  2. PL → ES,
  3. dyktando / pisanie,
  4. odsłuch (audio → znaczenie).

### 4.6 Ulubione vs obecnie uczone

- **Ulubione (♥):** bookmark — niekoniecznie w kolejce SRS.
- **Obecnie uczone (＋):** aktywna kolejka powtórek.

User może później przenieść ulubione do nauki jednym tapnięciem.

---

## 5. Agent AI — serce „szybkiego dodawania”

### 5.1 Rola agenta

Po wpisaniu słowa agent:

1. wykrywa język wejścia (PL/ES) i część mowy,
2. generuje listę kandydatów (tłumaczenia / lematy),
3. dla wybranego słowa (przy „＋” lub od razu w podglądzie) buduje **enrichment**:
   - znaczenia, synonimy, antonimy,
   - przykłady na poziomie CEFR usera,
   - użycia / kolokacje,
   - conjugación w wybranych czasach,
4. zwraca **ustrukturyzowany JSON** (nie luźny tekst) → zapis do Postgres.

### 5.2 Latencja „~2 sekundy”

Żeby było „szybkie i zajebiste”:

| Technika | Opis |
|----------|------|
| Dwuetapowość | najpierw szybka lista kandydatów (~0.5–1 s), enrichment pełny przy „＋” lub w tle |
| Cache | popularne słowa w Redis / tabeli cache (hash: słowo+kierunek+poziom+czasy) |
| Streaming | UI pokazuje skeleton → dopływa treść |
| Model | mały/szybki model do listy; mocniejszy do enrichmentu (lub jeden z dobrym promptem) |
| Prefetch TTS | audio generowane asynchronicznie po zapisie karty |

### 5.3 Jakość i bezpieczeństwo treści

- walidacja JSON schematem,
- filtr halucynacji: opcjonalnie cross-check ze słownikiem (np. zewnętrzne API / lokalna baza lematów),
- user może edytować kartę (korekta AI).

---

## 6. Propozycja technologii

### 6.1 Rekomendowany stack (MVP → skalowanie)

| Warstwa | Technologia | Dlaczego |
|---------|-------------|----------|
| **Mobile** | **Kotlin + Jetpack Compose** | natywny Android, prosty, ładny UI, dobra wydajność |
| **Backend API** | **NestJS (Node/TS)** lub **FastAPI (Python)** | NestJS: spójny TS z mobile-adjacent ekosystemem; FastAPI: wygodniej przy AI/LLM |
| **Baza** | **PostgreSQL** | relacje kart, znaczeń, SRS, userów — idealne |
| **ORM** | Prisma (Nest) / SQLAlchemy (FastAPI) | szybki development |
| **Auth** | JWT + refresh (email/hasło); opcjonalnie Firebase Auth | prosto i wystarczająco |
| **AI** | OpenAI / Anthropic API (structured outputs) | enrichment kart |
| **TTS** | Google Cloud TTS / Android TTS (offline fallback) | play przy ES |
| **Cache** | Redis (opcjonalnie w MVP: Postgres cache table) | przyspieszenie powtórzeń zapytań |
| **Hosting API+DB** | Railway / Fly.io / Supabase (Postgres) | szybki start |

**Rekomendacja spójna dla tego projektu:**

> **Android (Compose) → FastAPI → PostgreSQL → LLM (structured JSON) → TTS**

FastAPI lepiej „klei się” z pipeline’em AI (Python), a Postgres zostaje źródłem prawdy. Alternatywa all-TS: NestJS + Prisma — też OK, jeśli wolisz jeden język po stronie serwera webowego.

### 6.2 Alternatywy (jeśli chcesz cross-platform później)

- **Flutter** lub **React Native / Expo** — jeden kod Android+iOS,
- na MVP **natywny Android** jest prostszy i ładniejszy „out of the box”.

### 6.3 Czego unikać na start

- zbyt ciężkiego microservices (monolit API wystarczy),
- pełnego offline-first (można dodać później: Room + sync),
- własnego trenowania modeli NLP (API LLM + cache).

---

## 7. Architektura wysokopoziomowa

```
┌─────────────────┐     HTTPS/JSON      ┌──────────────────────┐
│  Android app    │ ◄─────────────────► │  API (FastAPI/Nest)  │
│  Jetpack Compose│                     │  auth, words, srs    │
└────────┬────────┘                     └──────────┬───────────┘
         │ play audio                               │
         ▼                                          ▼
┌─────────────────┐                     ┌──────────────────────┐
│ TTS (cloud lub  │                     │     PostgreSQL       │
│  systemowy)     │                     │ users, cards, reviews│
└─────────────────┘                     └──────────┬───────────┘
                                                   │
                                        ┌──────────▼───────────┐
                                        │  AI Agent (LLM)      │
                                        │  lookup + enrichment │
                                        └──────────────────────┘
```

### 7.1 Główne moduły backendu

1. **Auth** — rejestracja, logowanie, JWT  
2. **Profile / Settings** — L1, L2, poziom CEFR, wybrane czasy odmiany  
3. **Lookup** — wyszukiwanie słowa → lista kandydatów (AI + cache)  
4. **Cards** — tworzenie/edycja karty nauki, ulubione  
5. **SRS** — kolejkowanie powtórek, ocenianie  
6. **Audio** — URL/pliki wymowy lub proxy do TTS  
7. **Admin/Health** — monitoring, rate limit AI  

---

## 8. Model danych (szkic Postgres)

```text
users
  id, email, password_hash, created_at

user_settings
  user_id, native_lang, learning_lang, cefr_level,
  selected_tenses[], theme, ...

words_cache / lexical_entries   -- opcjonalny globalny cache AI
  id, language, lemma, pos, payload_json, created_at

favorite_words
  id, user_id, lexical_entry_id / lemma, created_at

learning_cards
  id, user_id,
  lemma_es, pos,
  meanings_json,      -- [{pl, examples[], usages[]}]
  synonyms_json,
  antonyms_json,
  conjugations_json,  -- wg selected_tenses
  notes,
  created_at, updated_at

srs_state
  card_id, user_id,
  ease, interval_days, repetitions, lapses,
  next_review_at, last_reviewed_at, status

review_logs
  id, card_id, user_id, grade, reviewed_at
```

Uwagi:

- na MVP dużo treści AI może żyć w **JSONB** (elastyczność),
- później normalizacja (tabele `meanings`, `examples`) gdy zajdzie potrzeba zapytań/analityki,
- unikalność: `(user_id, lemma_es, pos)` ≈ jedna karta nauki.

---

## 9. UI / UX — zasady

- **Jeden ekran = jeden job** (home / dodaj / wynik / karta / sesja).
- Duże CTA: *Dodaj słowo*, *Ćwicz*.
- Lista wyników: słowo ES + krótkie gloss PL + ♥ + ＋.
- Karta: sekcje zwijane (znaczenia → przykłady → odmiana → syn/ant).
- Play obok każdego ES (słowo / zdanie).
- Motyw: ciepły, czytelny, dużo powietrza; typografia czytelna do nauki; bez dashboardowego clutteru.
- Motions: krótkie przejścia listy, subtle reveal karty, feedback przy ocenie SRS.

---

## 10. Analiza pomysłu — mocne strony i ryzyka

### Mocne strony

- jasna różnica vs Anki: **AI robi ciężką robotę**,
- flow „wpadło mi słowo → 2 s → mam kartę” jest uzależniający,
- bogaty kontekst zwiększa retencję,
- Postgres + SRS = solidny fundament sync / multi-device później.

### Ryzyka

| Ryzyko | Mitygacja |
|--------|-----------|
| Halucynacje AI (złe tłumaczenie) | structured output + możliwość edycji + cache zweryfikowanych kart |
| Koszt LLM / TTS | cache agresywny, enrichment dopiero przy „＋” |
| Latencja > 2 s | dwuetapowe UI, streaming, szybki model do lookup |
| Przeładowanie karty informacją | sekcje, progressive disclosure |
| Scope creep | twarde MVP (sekcja 11) |

---

## 11. Zakres MVP (v0.1)

Must-have:

1. Rejestracja / logowanie (email + hasło)  
2. Ustawienia: PL/ES, poziom, wybrane czasy  
3. Home: Dodaj / Ćwicz  
4. Lookup słowa + lista wyników + ♥ / ＋  
5. Generowanie karty AI (znaczenia, 1–2 przykłady, syn/ant, podstawowa conjugación)  
6. Sesja SRS uproszczona (ES→PL)  
7. Play audio (choćby Android TTS)  
8. Postgres jako źródło prawdy  

Out of scope MVP (później):

- iOS / web,
- tryby pisania / dyktando,
- społecznościowe talie,
- OCR z książki / aparat,
- pełny offline,
- własne modele.

---

## 12. Roadmapa rozwoju (po MVP)

1. **Jakość AI** — weryfikacja słownikowa, preferencje stylu przykładów  
2. **Więcej trybów ćwiczeń** — PL→ES, cloze, listening  
3. **Statystyki** — streak, liczba kart due, heatmap  
4. **Offline + sync** (Room)  
5. **Więcej par językowych**  
6. **Import z Anki / CSV**  
7. **Widget Android** — „słowo dnia” / due reviews  
8. **Agent konwersacyjny** — „użyj tego słowa w dialogu”  

---

## 13. Organizacja projektu (żeby leciało szybko)

### 13.1 Kolejność prac

1. Schema Postgres + auth  
2. Endpoint lookup (mock AI → prawdziwy LLM)  
3. Zapis karty + ulubione  
4. SRS scheduler + endpoint „due cards”  
5. Android: home → add → results → card  
6. Android: practice session  
7. TTS  
8. Szlify UX + cache  

### 13.2 Kontrakt AI (przykład JSON)

```json
{
  "input": "pusty",
  "input_lang": "pl",
  "candidates": [
    {
      "lemma": "vacío",
      "pos": "adj",
      "gloss_pl": "pusty, próżny",
      "preview": true
    }
  ]
}
```

Enrichment przy dodaniu:

```json
{
  "lemma": "vacío",
  "pos": "adj",
  "meanings": [
    {
      "pl": "pusty (niezawierający nic)",
      "examples": [
        {
          "es": "La botella está vacía.",
          "pl": "Butelka jest pusta.",
          "level": "A2"
        }
      ],
      "usages": ["estar vacío", "espacio vacío"]
    }
  ],
  "synonyms": ["desocupado", "hueco"],
  "antonyms": ["lleno", "pleno"],
  "conjugations": null,
  "notes": null
}
```

---

## 14. Metryki sukcesu

- czas od wpisania słowa do listy wyników **< 2 s** (p50),  
- czas do pełnej karty po „＋” **< 3–4 s** (lub progressive),  
- user dodaje ≥ N słów / tydzień bez porzucenia flow,  
- retencja powtórek (SRS completion rate).

---

## 15. Otwarte pytania do wspólnego doprecyzowania

1. Czy lookup ma **zawsze** iść przez AI, czy najpierw lokalny/cache słownik?  
2. Czy enrichment pełny od razu na liście, czy dopiero po „＋”? (rekomendacja: po „＋”)  
3. Czy ulubione mają osobną kolejkę nauki, czy tylko bookmark?  
4. Czy edycja karty przez usera jest w MVP?  
5. Auth: tylko email, czy od razu Google?  
6. Nazwa produktu ostateczna: **Vocabulario** OK?  
7. Czy czasy conjugación wybieramy globalnie w ustawieniach, czy per karta?  

---

## 16. Podsumowanie decyzji (do aktualizacji)

| Temat | Status | Decyzja |
|-------|--------|--------|
| Platforma | propozycja | Android natywny (Compose) |
| Backend | propozycja | FastAPI + PostgreSQL |
| AI | propozycja | LLM + structured JSON + cache |
| Auth MVP | propozycja | email + hasło + JWT |
| SRS | propozycja | uproszczony SM-2 |
| Enrichment | propozycja | przy akcji „＋”, nie przy samym search |
| Dokument | living | ten plik w `doc/` |

---

*Ostatnia aktualizacja: start planu — wspólne doprecyzowanie w toku.*
