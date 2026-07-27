# Vocabulario (repo) — plan aplikacji do nauki słówek

Dokument roboczy do wspólnego planowania. **Nazwa repo:** `vocabulario`. **Nazwa produktu/aplikacji:** do wymyślenia później.

---

## 1. Wizja produktu

Prosta aplikacja **Android** do nauki słówek, która łączy:

- **błyskawiczne dodawanie** (wpisz → AI przygotuje kartę w ~2 s),
- **bogatą, czytelną kartę słowa** (znaczenia, synonimy, antonimy, przykłady, odmiana, użycia),
- **SRS** (powtórki rozłożone w czasie) z kilkoma trybami odpowiedzi,
- **wymowę** (play przy słowach i zdaniach w języku nauki),
- później: **tryb nauczyciela** (listy słówek, eksport, śledzenie postępów ucznia).

Cel UX: otworzyć → dodać lub ćwiczyć → wrócić do nauki. Zero mozolnego przygotowywania fiszek.

**Core MVP = flow nauki:** dodawanie AI + sesja SRS muszą działać razem.

---

## 2. Problem, który rozwiązujemy

Klasyczne fiszki (Anki itd.):

- wymagają ręcznego tworzenia kart,
- często są „suche” (słowo → tłumaczenie),
- kontekst, odmiana i użycia trzeba dokładać samemu.

Chcemy odwrotności: **user podaje impuls** („pusty”), **AI + backend budują kompletną kartę**, user tylko zatwierdza (♥ / ＋).

---

## 3. Języki, konfiguracja, onboarding

| Założenie | Decyzja |
|-----------|--------|
| Para języków | **dowolna** — przy rejestracji user wybiera język ojczysty (L1) i język nauki (L2) |
| Wiele języków nauki | tak — user może mieć wiele par / konfiguracji i przełączać |
| UI aplikacji | wielojęzyczny (język interfejsu wybierany przez usera) |
| Start aplikacji | zawsze w **ostatnio używanej konfiguracji** (ta z chwili ostatniego zamknięcia) |
| Pierwsze uruchomienie | po rejestracji: wybór L1 + L2 (+ poziom CEFR, czasy odmiany) |
| Platforma MVP | Android |
| UI | wizualnie miły, maksymalnie prosty |

Przykład użycia: PL→ES dziś, jutro PL→EN — po restarcie wraca do ostatniej pary.

---

## 4. Główne flow aplikacji

### 4.1 Ekran startowy (Home) — DECYZJA

Dwa duże przyciski:

1. **Dodaj słowo**
2. **Ćwicz**

Dyskretnie: ulubione, obecnie uczone, ustawienia, profil, przełącznik aktywnej pary językowej.

### 4.2 Rejestracja / logowanie — DECYZJA

- **Email + hasło** oraz **Google Sign-In od razu** (MVP).
- Po rejestracji: onboarding językowy (L1, L2, poziom, czasy).

### 4.3 Dodaj słowo — wyszukiwanie

1. Aktywna konfiguracja: L1 + L2 (ostatnio używana / wybrana).
2. User wpisuje słowo; system wykrywa kierunek względem aktywnej pary (L1→L2 lub L2→L1).
3. Backend + AI zwracają **szybką listę kandydatów** (krótki gloss).
4. **Pełny enrichment AI dopiero po ＋** (nie na liście).

#### Gdy wpisano słowo w L1 (np. PL „pusty”)

- lista 1+ odpowiedników w L2,
- przy każdym: **♥** (ulubione) i **＋** (do obecnie uczonych + pełna karta).

#### Gdy wpisano słowo w L2 (np. ES „vacío”)

- lemat L2 + znaczenia w L1,
- te same **♥** / **＋**.

### 4.4 Ulubione vs obecnie uczone — DECYZJA

- **♥ Ulubione:** tylko bookmark (bez SRS), można później dodać ＋.
- **＋ Obecnie uczone:** tworzy rekord karty + wchodzi do kolejki SRS.

### 4.5 Karta słowa (po ＋)

| Pole | Opis |
|------|------|
| Lemat L2 | forma bazowa |
| Część mowy | verb / noun / adj / … |
| Synonimy / antonimy | gdy ma sens (szczególnie rzeczowniki, przymiotniki) |
| Znaczenia L1 | osobno |
| Przykłady | **2 zdania na znaczenie**, poziom CEFR usera + tłumaczenie L1 |
| Oboczność / warianty | gdy istotne |
| Najczęstsze użycia | kolokacje, charakterystyczne wypowiedzi |
| Odmiana | czasy **globalnie** z ustawień usera |
| Audio | play przy L2 (słowa i zdania) |

**Edycja karty przez usera:** później (nie MVP).

### 4.6 Nauka (Ćwicz) + SRS — DECYZJA

#### Oceny po odpowiedzi

Trzy poziomy (mapowane na SRS):

1. **Trudne**
2. **Łatwe**
3. **Znam dobrze**

#### Kierunek i forma odpowiedzi — wybór usera lub losowo

User w ustawieniach / na starcie sesji decyduje (lub „losuj”):

| Tryb | Opis |
|------|------|
| Wybór zamknięty | pokazuje się słowo (L1 lub L2) + **8 opcji**, z czego 1 poprawna |
| Wpisz | user wpisuje odpowiedź |
| Powiedz | rozpoznawanie mowy (po TTS/free path; jakość do ustalenia) |

**Kierunki:** L2→L1 oraz L1→L2 (np. polskie słowo → wybrać/wpisać hiszpańskie; hiszpańskie → wpisać polskie).

#### Generowanie 8 opcji (wybór zamknięty)

Skład zestawu (kolejność losowa):

1. **1×** poprawna odpowiedź  
2. **3×** z katalogu *obecnie uczonych* (ta sama część mowy, o ile możliwe)  
3. **4×** dystraktory: ta sama część mowy + podobne brzmienie / pisownia do szukanego  

Cel: nie ma być „łatwizny”.

#### Feedback przy błędzie

- **Wybór zamknięty (złe zaznaczenie):** mały modal — co oznacza wybrane (błędne) słowo; jeśli nie ma go na liście nauki → buttony **♥** / **＋**.
- **Wpisanie z drobną pomyłką:** tolerancja literówek / znaków specjalnych (do doprecyzowania algorytmu); akceptuj z korektą w modalu: *„wpisałeś X, powinno być Y — zwróć uwagę”*. Modal korekty można **wyłączyć w ustawieniach**.

#### Co trafia do sesji „Ćwicz”? (wyjaśnienie pkt 14)

SRS działa tak, że każda karta ma datę **`next_review_at`** (kiedy znów ją pokazać).

| Pojęcie | Znaczenie |
|---------|-----------|
| **Due** | karty, których termin powtórki już nadszedł (albo nowe, jeszcze niećwiczone wg reguł) |
| **Nowe** | dopiero dodane ＋, jeszcze bez historii powtórek |
| **Później** | karty z `next_review_at` w przyszłości — SRS mówi „nie ruszaj dziś” |

**Pytanie do Ciebie (do decyzji):** po kliknięciu **Ćwicz** pokazywać:

- **A)** tylko karty *due* (klasyczny Anki — uczysz to, co „zaplanowane na teraz”), czy  
- **B)** due + możliwość dokładać nowe od razu w tej samej sesji, czy  
- **C)** user wybiera na starcie sesji: „powtórki” / „tylko nowe” / „miks”?

**Propozycja:** **C** (elastycznie), domyślnie miks due+nowe z limitem nowych/dzień.

---

## 5. Agent AI

### 5.1 Rola

1. wykrywa język wejścia i część mowy względem aktywnej pary,
2. szybka lista kandydatów,
3. po ＋: enrichment (znaczenia, 2 przykłady/znaczenie, syn/ant, użycia, odmiana),
4. structured JSON → Postgres (+ lokalny cache na urządzeniu do offline nauki).

### 5.2 Latencja

| Technika | Opis |
|----------|------|
| Dwuetapowość | lista szybka → enrichment przy ＋ |
| Cache | popularne lookup/enrichment w DB/Redis |
| Streaming / skeleton | UI nie „wisi” |
| Prefetch audio | TTS async po zapisie |

### 5.3 Jakość

- walidacja JSON,
- później: edycja usera, cross-check słownikowy.

---

## 6. Offline — DECYZJA

| Funkcja | Online | Offline |
|---------|--------|--------|
| Dodaj słowo (AI lookup/enrichment) | tak | **nie** |
| Ćwicz na już dodanych kartach | tak | **tak** (rekord w lokalnej bazie) |
| Sync postępów SRS | gdy net wróci | kolejka sync |
| Część funkcji (AI, nowe listy od nauczyciela, cloud TTS…) | tak | może nie działać |

Zasada: **jak słowo już dodane → rekord lokalny → nauka offline OK.**

---

## 7. Technologia — DECYZJA KIERUNKU

Priorytet: **żeby było bardzo szybkie w developmentcie i w runtime.**

| Warstwa | Wybór | Dlaczego |
|---------|-------|----------|
| Mobile | **Kotlin + Jetpack Compose** | natywna szybkość UI na Androidzie |
| Lokalna baza | **Room** | offline nauka + sync |
| Backend | **FastAPI (Python)** | najszybszy glue do LLM |
| DB | **PostgreSQL** | prawda serwerowa |
| Auth | email/hasło + **Google** | od razu |
| AI | LLM structured outputs | enrichment |
| TTS MVP | **Android system TTS** (darmowe) | cloud TTS później |
| Cache | Postgres table → Redis gdy trzeba | |

> **Android Compose + Room → FastAPI → PostgreSQL → LLM → system TTS**

---

## 8. Architektura

```
┌──────────────────────┐     HTTPS      ┌──────────────────────┐
│  Android (Compose)   │ ◄────────────► │  FastAPI             │
│  Room (offline cards)│                │  auth, lookup, srs   │
└──────────┬───────────┘                └──────────┬───────────┘
           │ TTS systemowy                          │
           ▼                                        ▼
┌──────────────────────┐                ┌──────────────────────┐
│  Android TTS         │                │  PostgreSQL          │
└──────────────────────┘                └──────────┬───────────┘
                                                   ▼
                                        ┌──────────────────────┐
                                        │  AI Agent (LLM)      │
                                        └──────────────────────┘
```

Moduły API: Auth, Settings/Languages, Lookup, Cards, Favorites, SRS, Audio meta, (później) Teacher.

---

## 9. Model danych (szkic)

```text
users
  id, email, password_hash, google_id, ui_lang, created_at

language_profiles          -- wiele par na usera
  id, user_id, native_lang, learning_lang, cefr_level,
  selected_tenses[], last_used_at, is_last_active

user_settings
  user_id,
  practice_input_pref,     -- choice | type | speak | random
  typo_modal_enabled,
  ...

lexical_cache
  id, lang_pair, input, payload_json, created_at

favorite_words
  id, user_id, profile_id, lemma, pos, gloss, created_at

learning_cards
  id, user_id, profile_id,
  lemma_l2, pos,
  meanings_json,           -- 2 examples each
  synonyms_json, antonyms_json,
  conjugations_json,
  created_at, updated_at

srs_state
  card_id, ease, interval_days, repetitions, lapses,
  next_review_at, last_reviewed_at, status

review_logs
  id, card_id, grade, mode, reviewed_at

-- później: teacher / classroom
teachers, students, class_groups, assigned_word_lists,
student_progress_snapshots
```

---

## 10. UI / UX

- Home = jedna kompozycja, 2 CTA.
- Lista wyników lekka; bogactwo na karcie po ＋.
- Sekcje zwijane na karcie.
- Play przy L2.
- Modale feedbacku: krótkie, wyłączalne (korekta literówek).
- Dużo powietrza, czytelna typografia, bez clutteru.

---

## 11. Zakres MVP vs później — wyjaśnienie pkt 19

**MVP (v0.1)** = najmniejsza wersja, w której **core nauki działa**:

1. Auth: email + Google  
2. Onboarding L1/L2 + zapamiętanie ostatniej konfiguracji  
3. Home: Dodaj / Ćwicz  
4. Lookup AI + ♥ / ＋ + enrichment (2 przykłady/znaczenie)  
5. Sesja ćwiczeń: wybór zamknięty (8 opcji) + wpisywanie; oceny trudne/łatwe/znam dobrze  
6. Lokalny zapis kart → nauka offline  
7. System TTS  

**Świadomie później (nie blokuje core):**

| Później | Dlaczego nie w pierwszym buildzie |
|---------|-----------------------------------|
| iOS / web | najpierw Android |
| Tryb „powiedz” (speech-to-text) | trudniejszy technicznie; najpierw wybór + wpisz |
| Edycja karty | potwierdzone: później |
| Cloud TTS premium | najpierw darmowy systemowy |
| Pełny panel nauczyciela | duży osobny moduł — zaplanowany, ale etap 2 |
| OCR z aparatu, import Anki, widgety | nice-to-have |

To nie znaczy „nigdy” — tylko **kolejność**: najpierw core flow nauki, potem rozszerzenia.

---

## 12. Tryb nauczyciela (backlog — do doprecyzowania)

Cel: apka użyteczna też dla lektorów.

Proponowany zakres (etap 2+):

- nauczyciel tworzy / importuje **listę słówek**,
- przypisuje listę uczniowi / grupie,
- uczeń dostaje słowa do ♥/＋ lub od razu do nauki,
- nauczyciel widzi **postępy** (ile due, accuracy, streak, które słowa słabe),
- eksport (CSV / link / kod klasy).

**Pytania otwarte — nauczyciel:** patrz sekcja 16.

---

## 13. Roadmapa

1. **v0.1 Core** — auth, języki, dodaj AI, Ćwicz (choice+type), SRS, offline read/practice, TTS  
2. **v0.2** — speech mode, lepsza tolerancja literówek, szlify UX, cache AI  
3. **v0.3 Teacher** — listy, przypisania, podstawowy progress  
4. **v0.4** — edycja kart, cloud TTS, statystyki ucznia, iOS/web jeśli potrzeba  

---

## 14. Organizacja prac (szybkie tempo)

1. Schema Postgres + auth (email+Google) + language profiles  
2. Lookup mock → LLM  
3. Cards + favorites + Room sync skeleton  
4. SRS + practice engines (multiple choice 8 + type-in)  
5. Android UI: home → add → results → practice  
6. Offline practice path  
7. TTS systemowy  
8. Szlify + cache  

### Kontrakt AI (skrót)

Lookup → kandydaci z krótkim gloss.  
Enrichment przy ＋ → pełny JSON (meanings z **2** examples, syn/ant, usages, conjugations).

---

## 15. Metryki sukcesu

- lookup lista **< ~2 s** (p50),  
- enrichment po ＋ **< ~3–4 s** (lub progressive),  
- core: user może dodać słowo i od razu ćwiczyć,  
- offline: powtórka działa bez netu na zapisanych kartach.

---

## 16. Otwarte pytania (odpisz punktami)

### Sesja Ćwicz (dokończenie pkt 14)
1. Po **Ćwicz** domyślnie: **A** tylko due / **B** due+nowe / **C** user wybiera (powtórki / nowe / miks)?  
   **Propozycja: C, domyślnie miks.**

### Ćwiczenia
2. Tryb **„powiedz”** w MVP czy od v0.2?  
   **Propozycja: v0.2** (najpierw wybór 8 + wpisz).
3. Tolerancja literówek: akceptować błąd 1 znaku / brak znaków diakrytycznych (ñ, ó…) jako „prawie OK” z modalem korekty — zgoda?
4. Przy wpisywaniu L1 (np. polski): czy synonimy znaczenia też uznajemy (np. „pusty” vs „próżny”), czy tylko kanoniczne gloss z karty?

### Nauczyciel
5. Nauczyciel to osobne konto/rola w tej samej apce, czy osobny panel web?
6. Uczeń łączy się kodem klasy / emailem / linkiem?
7. Lista od nauczyciela: wpada jako propozycje do dodania, czy od razu jako karty w SRS ucznia?
8. Jakie minimum podglądu postępów dla nauczyciela w v0.3? (np. % opanowanych, słowa trudne, ostatnia aktywność)

### Produkt
9. Język UI na start: tylko PL+EN, czy od razu więcej?
10. Limit nowych kart / dzień — wprowadzamy od razu (chroni przed przeładowaniem SRS)?

---

## 17. Podsumowanie decyzji (aktualne)

| Temat | Status | Decyzja |
|-------|--------|--------|
| Nazwa repo | OK | `vocabulario`; nazwa apki później |
| Języki | OK | dowolne L1/L2 przy rejestracji; wiele; last-used przy starcie |
| Home | OK | Dodaj / Ćwicz |
| ♥ / ＋ | OK | bookmark vs nauka+enrichment |
| Enrichment | OK | dopiero po ＋; 2 przykłady na znaczenie |
| Conjugación | OK | globalnie w ustawieniach |
| Edycja karty | OK | później |
| CEFR | OK | globalny poziom → zdania |
| Ćwiczenia | OK | user/losowo; choice 8 / wpisz / (powiedz później?); feedback+modale |
| Dystraktory | OK | 1 correct + 3 learning + 4 similar POS |
| Oceny SRS | OK | trudne / łatwe / znam dobrze |
| Stack | OK | Compose + Room + FastAPI + Postgres + LLM + system TTS |
| Auth | OK | email + Google od razu |
| Offline | OK | nauka tak, dodawanie AI nie |
| Core MVP | OK | flow nauki (AI add + SRS) |
| Nauczyciel | backlog | listy, przypisania, progress — etap 2+ |

---

*Ostatnia aktualizacja: decyzje z sesji Q&A + tryb nauczyciela + wyjaśnienia pkt 14/19.*
