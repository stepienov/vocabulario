# Vocabulario (repo) — plan aplikacji do nauki słówek

Dokument roboczy do wspólnego planowania. **Nazwa repo:** `vocabulario`. **Nazwa produktu/aplikacji:** do wymyślenia później.

---

## 1. Wizja produktu

Prosta aplikacja **Android** do nauki słówek, która łączy:

- **błyskawiczne dodawanie** (wpisz → AI przygotuje kartę w ~2 s),
- **bogatą, czytelną kartę słowa** (znaczenia, synonimy, antonimy, przykłady, odmiana, użycia),
- **SRS** z trybami odpowiedzi (wybór / wpisz / później powiedz),
- **wymowę** (play przy L2),
- później: **panel nauczyciela**, **smart przypomnienia**, inne release’e.

Cel UX: otworzyć → dodać lub ćwiczyć → wrócić do nauki.

**Core MVP = flow nauki:** dodawanie AI + sesja SRS.

---

## 2. Problem

Klasyczne fiszki = ręczna, sucha robota. Tu: user podaje impuls → AI buduje kartę → ♥ / ＋.

---

## 3. Języki i onboarding — DECYZJE

| Temat | Decyzja |
|-------|--------|
| Para L1/L2 | dowolna, wybór przy rejestracji |
| Wiele języków nauki | tak — przełączanie konfiguracji |
| Start apki | **ostatnio używana** konfiguracja (z chwili zamknięcia) |
| Język UI | **PL, EN + kilka najczęstszych** (propozycja startowa poniżej) |
| Platforma MVP | Android |

**Języki UI (v0.1):** PL, EN, ES, DE, FR, IT, PT, UK (ukraiński).  
Łatwo dodać kolejne później (pliki tłumaczeń).

---

## 4. Główne flow

### 4.1 Home

1. **Dodaj słowo**  
2. **Ćwicz**  

Dyskretnie: ulubione, obecnie uczone, listy/pakiety, ustawienia, profil, aktywna para językowa.

### 4.2 Auth — DECYZJA

Email + hasło **oraz Google** od razu. Potem onboarding L1/L2/CEFR/czasy.

### 4.3 Dodaj słowo

1. Aktywna para L1/L2.  
2. Wpis → wykrycie kierunku.  
3. Szybka lista kandydatów (krótki gloss).  
4. **Pełny enrichment dopiero po ＋.**

- L1 → lista odpowiedników L2 + ♥ / ＋  
- L2 → lemat + znaczenia L1 + ♥ / ＋  

**♥** = bookmark (bez SRS). **＋** = karta + kolejka nauki (enrichment).

### 4.4 Karta słowa (po ＋)

Lemat L2, POS, syn/ant, znaczenia L1, **2 przykłady na znaczenie** (CEFR), użycia, odmiana (czasy globalne), audio play.  
**Edycja karty:** później.

### 4.5 Ćwicz + SRS — DECYZJE

#### Kolejka po kliknięciu „Ćwicz”

Karty zgodnie z ustawieniami usera, w kolejności SRS:

1. **najpierw zaległe / due na dziś** (powtórki),  
2. **potem nowe** (w ramach limitu dziennego).

#### Limit nowych kart / dzień

| Parametr | Wartość |
|----------|---------|
| Default | **20 nowych / dzień** (jak Anki — bezpieczny start) |
| User może zmienić | tak (np. 5 / 10 / 20 / 50 / bez limitu) |
| Powtórki due | **bez limitu** |

#### Oceny

1. **Trudne**  
2. **Łatwe**  
3. **Znam dobrze**  

(nauczyciel później widzi te oznaczenia per słowo u ucznia)

#### Forma odpowiedzi

| Tryb | Zachowanie | Wersja |
|------|------------|--------|
| **Wybór (8 opcji)** | przód = słowo L1/L2; 8 odpowiedzi (1 poprawna + learning tej POS + `similar_words`) | v0.1 |
| **Wpisz** | przód = słowo; pole tekstowe + Enter | v0.1 |
| **Fiszki** | przód = samo słowo; klik → rewers (jak Anki) | v0.1 |
| Powiedz (speech) | — | **v0.2** |

Ustawienie: `practice_input_pref` = `choice` \| `type` \| `flashcard` \| `speak`.

#### Rewers fiszki (tryb „Fiszki”)

Układ (od góry):

1. **Sekcje znaczeń** (1–3) — każda zamknięta:
   - gloss + synonimy L1 w nagłówku (np. „kończyć, zakończyć, dokończyć”),
   - jedno zdanie L2 + tłumaczenie L1 (poziom z pasma CEFR usera),
   - przycisk **Przykłady użycia** → modal z `usages` (zamykanie tapnięciem poza treścią).
2. **Synonimy L2** (jeśli włączone w ustawieniach) — lemma + gloss; ♥ / ＋.
3. **Antonimy L2** (jw.).
4. **Peryfrazy** (jeśli włączone i czasownik) — formula + gloss + przykład.
5. **Odmiana** — tylko czasy z `selected_tenses` profilu; nagłówki rozwijane/zwijane; opcja „domyślnie rozwinięte”.

#### Widoczność sekcji na rewersie (ustawienia)

| Flaga | Default | Opis |
|-------|---------|------|
| `show_usages` | true | przycisk + modal usages przy znaczeniach |
| `show_synonyms_antonyms` | true | sekcje synonimów / antonimów |
| `show_periphrases` | true | blok peryfraz |
| `conjugation_expanded_default` | false | tabele odmiany startują rozwinięte |

Czasy widoczne w odmianie: `language_profiles.selected_tenses` (ekran Profil).

#### Kierunek karty (przód) — DECYZJA

User wybiera w ustawieniach (lub losowo), **co widać na przedniej stronie** przed odpowiedzią:

| Preferencja | Przód karty | User odpowiada |
|-------------|-------------|----------------|
| **L2 → L1** (default) | słowo w języku **uczanym** | znaczenie w L1 / rewers |
| **L1 → L2** | słowo / gloss w języku **ojczystym** | forma w L2 / rewers |
| **Losowo** | naprzemiennie / los | zgodnie z wylosowanym kierunkiem |

Ustawienie: `practice_direction` = `l2_to_l1` \| `l1_to_l2` \| `random`.  
Osobno od formy odpowiedzi (choice / type / flashcard / speak).

**8 opcji (kolejność losowa):** 1 poprawna + do 3 z obecnie uczonych (ta sama POS) + reszta z `similar_words` (ta sama POS), łącznie zawsze 8.

#### Tolerancja wpisywania — DECYZJA

Dwa osobne mechanizmy:

**A) Literówki** — ustawienie usera:

| Tryb | Zachowanie |
|------|------------|
| **Ściśle** | dokładna odpowiedź; i tak ignorujemy wielkość liter i zbędne spacje |
| **Toleruj błędy i poprawiaj** | drobne literówki / diakrytyki → uznaj + modal: *wpisałeś X, powinno być Y* |

**B) Synonimy znaczenia** — zawsze (niezależnie od A):

Przy trybie „Wpisz” (np. ES→PL) zaliczamy odpowiedź, jeśli zgadza się z **kanonicznym gloss albo synonimem zapisanym na karcie**.

Przykład: *vacío* ma na karcie „pusty” i „próżny” → **oba są poprawne**.  
Jeśli znaczenie faktycznie obejmuje dany synonim, ma trafić na kartę przy enrichment i być akceptowane przy wpisywaniu.

Nie odpalamy AI do oceny „czy sensownie” w trakcie odpowiedzi — tylko to, co jest na karcie (szybko i przewidywalnie).

Modal korekty literówek można wyłączyć osobno.

#### Feedback przy złym wyborze (8 opcji)

Modal: znaczenie wybranego (błędnego) słowa; jeśli nie ma w nauce → ♥ / ＋.

#### Ćwiczenia conjugación (czasowniki) — BACKLOG / późniejszy release

Dla **czasowników** nie tylko fiszki do zapamiętania znaczenia, ale też **dodatkowe zestawy ćwiczeń odmiany**:

- wpisywanie czasownika w odpowiedniej formie w zdaniu,
- / albo odmienianie w zadanym czasie (zgodnie z czasami wybranymi globalnie / poleconymi przez nauczyciela),
- nauczyciel może **polecać** takie zestawy uczniowi (osobny pakiet ćwiczeń).

Szczegóły UX i SRS dla conjugación — do doprecyzowania w osobnej sekcji przy release’ie.  
Na teraz: **jest w planie jako feature**, osobno od zwykłego zapamiętywania słówek.

---

## 5. Agent AI + wspólna baza leksykalna — DECYZJA

**Jedna duża, współdzielona baza słówek** (globalna dla wszystkich użytkowników). AI jest *fallbackiem*, nie pierwszym źródłem.

### Flow „Dodaj słowo”

1. User wpisuje tekst.  
2. Backend **najpierw szuka w naszej DB** (`lexical_entries` + indeksy / cache).  
3. **Hit** → zwracamy kandydatów / pełną kartę z bazy (szybko, bez kosztu AI).  
4. **Miss** → OpenAI (lookup → przy ＋ enrichment) → **od razu zapisujemy wynik do wspólnej bazy**, żeby kolejni userzy (i ten sam user) dostali to za darmo.  
5. Przy ＋ kopia trafia też do prywatnej `learning_cards` usera (SRS).

Im więcej osób dodaje słowa, tym baza się **sama zapełnia**. Seed startowy (poniżej) daje wartość od pierwszego uruchomienia.

Dwuetapowo przy miss AI: szybki lookup → enrichment przy ＋ (2 examples/znaczenie, syn/ant, usages, conjugations). Skeleton UI pod ~2 s.

---

## 6. Offline — DECYZJA

| Funkcja | Offline |
|---------|---------|
| Dodaj słowo (AI) | nie |
| Ćwicz na zapisanych kartach | **tak** |
| Sync SRS | gdy wróci net |
| Listy nauczyciela / część cloud | może nie działać |

---

## 7. Stack — DECYZJA

> **Android Compose + Room → FastAPI → PostgreSQL → LLM → system TTS (darmowy)**

Auth: email + Google. Cloud TTS / speech mode → późniejsze release’e.

---

## 8. Architektura (skrót)

App (Compose + Room) ↔ FastAPI ↔ Postgres + LLM.  
Lokalnie: karty + stan SRS do offline practice.

---

## 9. Model danych (szkic)

```text
users
  id, email, password_hash, google_id, ui_lang, created_at

language_profiles
  id, user_id, native_lang, learning_lang, cefr_level,
  selected_tenses[], last_used_at, is_last_active

user_settings
  user_id,
  practice_input_pref,      -- choice | type | flashcard | speak
  practice_direction,       -- l2_to_l1 | l1_to_l2 | random  (przód karty)
  typing_tolerance,         -- strict | tolerate_and_correct
  typo_modal_enabled,
  new_cards_per_day,        -- default 20
  show_usages,              -- bool, default true (modal usages na fiszce)
  show_synonyms_antonyms,   -- bool, default true
  show_periphrases,         -- bool, default true
  conjugation_expanded_default, -- bool, default false
  theme,
  ...

-- Wspólna baza leksykalna (globalna, rośnie z użyciem + seed)
lexical_entries
  id, lang_pair, lemma_l2, lemma_l1_primary, pos, cefr,
  content_json,             -- pełna karta (ten sam schemat co enrichment)
  source,                   -- seed | ai | curated
  created_by_user_id_nullable, usage_count, created_at

lexical_categories          -- kolory, liczebniki, conectores, ...
  id, slug, name_i18n

lexical_entry_categories    -- M:N entry ↔ category
  entry_id, category_id

starter_packs               -- gotowe zestawy do 1-klika „dodaj do nauki”
  id, slug, lang_pair, cefr_level, category_slug, title_i18n, sort_order

starter_pack_items
  pack_id, lexical_entry_id, sort_order

lexical_cache               -- szybki cache lookupów (klucz: input_norm)
  id, lang_pair, input_norm, kind, payload_json, created_at

favorite_words
  id, user_id, profile_id, lemma, pos, gloss, created_at

learning_decks              -- "pakiety" / listy (własne, starter, nauczyciel)
  id, user_id, profile_id, title, source,  -- personal | starter | teacher_list
  independent_srs,          -- true = osobny SRS; false = można merge do main
  created_at

learning_cards
  id, user_id, profile_id, deck_id_nullable,  -- null = główna lista nauki
  lexical_entry_id_nullable,-- link do wspólnej bazy (jeśli z niej)
  lemma_l2, pos,
  meanings_json, synonyms_json, antonyms_json,
  conjugations_json,
  created_at, updated_at

srs_state
  card_id, deck_scope,      -- main vs independent deck
  ease, interval_days, repetitions, lapses,
  next_review_at, last_reviewed_at,
  last_grade                -- hard | easy | know_well

review_logs
  id, card_id, grade, mode, reviewed_at

-- Teacher (release późniejszy)
teachers, classes, class_memberships,
teacher_word_lists, teacher_list_items,
list_assignments, student_progress_views
```

---

## 10. UI / UX

Home = 2 CTA. Lekka lista wyników. Bogata karta po ＋. Play przy L2. Krótkie modale. Bez clutteru.

---

## 11. Wersjonowanie — DECYZJA (dawny pkt 19)

Świadomie dzielimy na **release’e**. v0.1 = core. Reszta = dalsze featurę / wersje.

### v0.1 Core (MVP)

1. Auth email + Google (od razu)  
2. Onboarding L1/L2 + last-used config  
3. UI: PL, EN + kilka najczęstszych  
4. Home Dodaj / Ćwicz  
5. Lookup: **najpierw wspólna DB → potem AI**; ＋ enrichment; zapis do wspólnej bazy  
6. **Core priorytet:** jakość i kompletność karty po wpisaniu słowa (dopracowanie pipeline)  
7. Starter packs / seed CEFR×kategorie — **później**, po dopracowaniu kart  
8. Ćwicz: due/zaległe → nowe (limit); choice 8 + wpisz  
9. **Kierunek karty:** L2→L1 / L1→L2 / losowo (ustawienie usera)  
10. Tolerancja wpisywania: ścisłe / toleruj+poprawiaj  
11. Oceny: trudne / łatwe / znam dobrze  
12. Offline practice na zapisanych kartach  
13. System TTS  
14. Limit nowych (default 20, konfigurowalny)  

### Dalsze release’e (backlog)

| Feature | Orientacyjnie |
|---------|----------------|
| Tryb **powiedz** | v0.2 |
| Lepszy cache AI, szlify UX | v0.2 |
| **Ćwiczenia conjugación** (zdania / odmiana w czasie; polecane przez nauczyciela) | późniejszy release (po core; szczegóły później) |
| **Panel nauczyciela** (osobny, web) + listy/pakiety | v0.3 |
| **Smart przypomnienia** (push z treścią: trudne / do powtórki słowo już w notyfikacji) | późniejszy release |
| Edycja karty | później |
| Cloud TTS | później |
| iOS / web ucznia | później |
| OCR, import Anki, widgety | później |

---

## 12. Listy / pakiety + nauczyciel — DECYZJE

### Starter packs — PÓŹNIEJ (nie w pierwszym cięciu)

Gotowe zestawy (CEFR × kategorie: kolory, liczebniki, conectores, …) **zostają w planie**, ale **nie wgrywamy ich na start**.

Najpierw dopracowujemy do perfekcji **core: tworzenie pełnej karty** (wpisz słowo → OK → bogata, uporządkowana karta).  
Seed / starter packs dodajemy dopiero gdy pipeline karty będzie satysfakcjonujący.

Wspólna baza leksykalna (DB first → AI → zapis) **nadal obowiązuje** od początku — tylko bez curated seedów; baza rośnie z kart tworzonych przez AI / użytkowników.

### Panel nauczyciela

- **Osobny panel dodatkowy (web)** — nie wciśnięty w ten sam prosty UI ucznia.
- Nauczyciel tworzy listy słówek, przypisuje uczniom/grupom.
- Uczeń dołącza przez **kod klasy + link**.
- Widzi per uczeń / per słowo oceny: **trudne / łatwe / znam dobrze**.

### Jak uczeń korzysta z listy

Lista to osobny byt. User może:

1. **Dodać wszystkie** elementy listy do swojej głównej nauki, albo  
2. **Dodać wybrane**, albo  
3. **Uczyć się listy osobno** — jak **niezależny pakiet z własnym SRS** (nie miesza się z główną kolejką).

To samo podejście działa dla **starter packs**, list własnych i od nauczyciela.

### Ćwiczenia conjugación a nauczyciel

Nauczyciel może polecać nie tylko listy słówek, ale też **zestawy ćwiczeń odmiany** (dla czasowników z listy / pakietu): uzupełnianie formy w zdaniu, trening wybranego czasu itd.  
Szczegóły mechaniki — przy projektowaniu release’u conjugación.

---

## 13. Smart przypomnienia (przyszły release)

Push / lokalne powiadomienia, które **od razu niosą treść**:

- słowo oznaczone jako **trudne**, albo  
- słowo **due do powtórki**,  

np. „¿Cómo se dice *pusty*? → …” / mini-quiz w notyfikacji.  
Nie tylko „masz 12 kart do powtórki”, tylko konkretny materiał.

---

## 14. Roadmapa

1. **v0.1 Core** — auth, języki, AI add, Ćwicz (choice+type), SRS kolejka due→new, offline, TTS, limit  
2. **v0.2** — powiedz, tolerancja/UX, cache  
3. **v0.3 Teacher** — panel web, listy, przypisania, podgląd trudne/łatwe/znam dobrze  
4. **v0.4+** — ćwiczenia conjugación (zdania/odmiana; polecenia nauczyciela), smart przypomnienia, edycja kart, cloud TTS, iOS/web…

---

## 15. Organizacja prac (v0.1)

1. Schema + auth + language profiles + settings (+ `practice_direction`)  
2. Wspólna baza `lexical_entries` + seed packs (CEFR × kategorie)  
3. Lookup: DB first → LLM fallback → zapis do wspólnej bazy  
4. Cards + favorites + Room  
5. SRS scheduler (due first → new within limit)  
6. Practice: multiple choice 8 + type-in + tolerance + kierunek karty  
7. Android UI (Home, Dodaj, Ćwicz, Starter packs)  
8. Offline practice  
9. TTS + szlify  

---

## 16. Metryki

- lookup < ~2 s, enrichment < ~3–4 s,  
- core flow działa end-to-end,  
- offline powtórka na zapisanych kartach.

---

## 17. Decyzje domknięte (wcześniej otwarte)

| # | Temat | Decyzja |
|---|-------|--------|
| 1 | Akceptacja przy wpisywaniu | **B — kanoniczne gloss + synonimy z karty** (nie pełne AI fuzzy) |
| 2 | Łączenie uczeń↔nauczyciel | **kod klasy + link** |
| 3 | Języki UI start | **PL, EN, ES, DE, FR, IT, PT, UK** |
| 4 | Limit nowych | **default 20**, user zmienia |
| 5 | Limit powtórek due | **bez limitu** |
| 6 | Tryb ścisły — normalizacja | **tak:** ignoruj wielkość liter i zbędne spacje |
| 7 | Wspólna baza leksykalna | **DB first → OpenAI fallback → zapis do wspólnej DB** |
| 8 | Seed na start | **później** — najpierw dopracowanie tworzenia pełnej karty |
| 9 | Kierunek karty (przód) | **l2_to_l1 \| l1_to_l2 \| random** (ustawienie usera) |
| 10 | Auth | email + Google od razu |

### Wyjaśnienie pkt 1 (akceptacja wpisanej odpowiedzi)

Chodzi tylko o tryb **„Wpisz”**, gdy apka pokazuje np. hiszpańskie *vacío* i pyta o znaczenie po polsku.

Na karcie AI zapisuje np.:

- główne znaczenie (kanoniczne): **pusty**
- synonimy tego znaczenia na karcie: **próżny**, **niepełny** (przykład)

User wpisuje odpowiedź. Co uznajemy za dobrą?

| Opcja | Zachowanie | Przykład |
|-------|------------|----------|
| A | tylko dokładne kanoniczne gloss | zalicza tylko „pusty” |
| **B (wybrane)** | kanoniczne **albo** synonim **z tej karty** | zalicza „pusty” i „próżny”, jeśli oba są na karcie |
| C | AI ocenia sens swobodnie | droższe, wolniejsze, mniej przewidywalne |

**Wybrane B:** uczciwie wobec tego, czego uczy karta, bez odpalania AI przy każdej odpowiedzi.

Uwaga: to jest osobne od ustawienia **ściśle / toleruj literówki** (to dotyczy literówek typu `pustyy` / brak `ó`). Synonimy = inne poprawne słowo-znaczenie z karty.

---

## 18. Podsumowanie decyzji

| Temat | Decyzja |
|-------|--------|
| Nazwa apki | tymczasowo **Vocabulario**; docelowa później |
| Identyfikator pakietu Android | tymczasowy; docelowy przed publikacją |
| L1/L2 | dowolne; last-used przy starcie |
| Home | Dodaj / Ćwicz |
| Wspólna baza | **TAK** — jedna globalna `lexical_entries`; rośnie z AI (i seedem później) |
| Lookup | **najpierw DB**, potem OpenAI; wynik AI → zapis do DB |
| Priorytet core | **jakość pełnej karty** po wpisaniu słowa — dopracować do perfekcji |
| Seed / gotowe zestawy | **później**, po akceptacji jakości kart |
| Enrichment | po ＋; bogata, uporządkowana karta |
| Ćwicz kolejka | zaległe/due dziś → potem nowe |
| Limit nowych | default **20**, user zmienia |
| Powtórki due | bez limitu |
| Oceny | trudne / łatwe / znam dobrze |
| Odpowiedzi v0.1 | choice 8 + wpisz; powiedz = v0.2 |
| Kierunek karty | **l2_to_l1 \| l1_to_l2 \| random** (ustawienie usera) |
| Tolerancja literówek | ustawienie: ściśle \| toleruj i poprawiaj |
| Akceptacja znaczeń (wpisz) | kanoniczne + synonimy **z karty** (np. pusty/próżny) |
| Normalizacja ścisła | case + spacje ignorowane |
| Auth | email + Google **od razu** |
| Offline | nauka tak, AI add nie |
| UI lang | PL, EN, ES, DE, FR, IT, PT, UK |
| Nauczyciel | osobny panel web; listy jako pakiety |
| Lista u ucznia | all / wybrane → main, albo osobny SRS pakiet |
| Join klasy | kod + link |
| Progress dla nauczyciela | widać trudne/łatwe/znam dobrze |
| Conjugación drills | późniejszy release |
| Przypomnienia smart | przyszły release |
| Featurę poza core | dalsze wersje / release’e |

---

*Ostatnia aktualizacja: Google od razu; seed odłożony; priorytet = jakość tworzenia kart.*
