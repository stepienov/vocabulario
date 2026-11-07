# Optymalizacja długich żądań

Dokument roboczy na sesję 7 listopada 2026. Zbiera fakty z produkcji, opis tego, co użytkownik czeka, i zamknięte decyzje naprawy. Kod ruszamy dopiero wtedy, gdy ten plik opisze wszystkie żądania z kolejki.

Pomiary pochodzą z produkcji `https://vocabulario.up.railway.app`, bazy Postgres na Railway i logów `app_logs` / `lookup_events` / `llm_usage`. Konto kontrolne: `nowy4@test.com`, włączony profil polski → hiszpański (`pl>es`). Deploy, na którym to mierzono: 2 listopada 2026, commit `33a3b6d`.

## Jak czytać czasy

„Całe żądanie” to jedna wycieczka HTTP. Telefon wysyła słowo, proces API przyjmuje je, wykonuje kod i odsyła JSON. Czas w `app_logs.duration_ms` liczy się w tym procesie, od wejścia w obsługę do chwili, gdy odpowiedź jest gotowa. Nie wlicza drogi telefonu do Railway ani zapisu samego wiersza logu, który powstaje już po odpowiedzi.

Czas wykonania SQL (`EXPLAIN ANALYZE`) to co innego: praca samej bazy, bez drogi z procesu API do Postgresa. Przy `prado` odczyt wiersza cache trwał w bazie **0,07 ms**, a całe żądanie na serwerze **3,0–3,5 s**.

Z komputera, z którego robione było śledztwo, jedna podróż do tej samej bazy (`SELECT 1` i odczyt wiersza `prado`) trwa około **410 ms**. To droga sieciowa tego komputera, nie czas bazy i nie czas procesu API. Pokazuje rząd wielkości czekania, gdy pytający nie siedzi tuż przy Postgresie.

## Kolejka

| # | Co czeka użytkownik | Stan |
|---|---------------------|------|
| 1 | Szybkie szukanie, gdy odpowiedź jest już zapisana | decyzja podjęta, implementacja czeka |
| 2 | Szybkie szukanie, gdy zapisu jeszcze nie ma | nieanalizowane |
| 3 | Dociągnięcie pełnej listy propozycji | nieanalizowane |
| 4 | Szukanie kategorii | nieanalizowane |
| 5 | Zapis karty po wybraniu propozycji | nieanalizowane |
| 6 | Dociąganie treści karty po zapisie | nieanalizowane |
| 7 | Import listy słów | nieanalizowane |

Żądanie 1 świadomie nie zmienia szukania bez zapisu, dociągania modelem, kategorii, zapisu karty ani importu.

---

## 1. Szybkie szukanie gotowej odpowiedzi

### Co użytkownik robi

Wpisuje słowo w dodawaniu i czeka na listę propozycji. Jeśli to hasło było już kiedyś dokończone, ma dostać zapisane propozycje i na tym skończyć. Nie ma wołać modelu i nie ma kręcić dalszego czekania.

Słowo próbne: samo `prado`. Zapis dla `pl>es` jest dokończony, ma trzy propozycje (`el prado`, `el derecho`, `la ley`) i był wielokrotnie użyty. `el prado` jest innym hasłem i do tego testu nie służy.

### Jak to działa dzisiaj

Telefon, po zatwierdzeniu słowa, woła `POST /api/v1/lookup/cached`.

Serwer (`LexicalService.lookup_cached`):

1. Ładuje użytkownika z tokenu (`get_current_user`).
2. Ładuje profil.
3. Normalizuje wpis (małe litery, bez znaków diakrytycznych, obcięte do 200 znaków) i szuka jednego wiersza w `lookup_query_cache` po parze języków i tym kluczu.
4. Jeśli wiersz jest i ma propozycje albo flagę „dokończone” (`ai_complete`), podbija licznik użyć i składa odpowiedź w `_present_lookup`. Na tym ta gałąź się kończy. Wikisłownik i modele nie startują.
5. Składanie odpowiedzi układa propozycje w pamięci, dociąga identyfikatory haseł z `lexical_entries` i czyta karty oraz listy użytkownika, żeby dopisać, czy dana propozycja jest już w nauce.
6. Endpoint dopisuje wiersz historii w `lookup_events` i robi commit. Commit niesie też zapis licznika użyć.

Dopiero JSON wraca do telefonu. Telefon (`LookupSession.applyCachedOutcome`) pokazuje propozycje. Gdy flaga „dokończone” jest prawdziwa, nie woła dociągania.

Równolegle `LookupCoordinator.start` zawsze kolejkuje `LookupPollWorker`. Worker od razu woła to samo szybkie szukanie jeszcze raz. Przy gotowej odpowiedzi ta druga wycieczka nic nie wnosi: ekran i tak kończy po pierwszej.

Zapisane propozycje w cache mają tylko `lemma`, `pos` i `gloss`. Przy `prado` nie ma w JSON identyfikatora hasła ani informacji o nauce. Jedno i drugie jest dokładane przy każdej odpowiedzi.

### Fakty z produkcji

Test `prado`, 7 listopada 2026, około 09:50 UTC. Pięć żądań `POST /api/v1/lookup/cached`, wszystkie `source=db`, `ai_complete=true`, 3 propozycje. Żadnego wpisu w `llm_usage`.

| Start (z `lookup_events`, czas transakcji) | Czas całego żądania |
|---|---:|
| 09:50:07.507 | 3019 ms |
| 09:50:07.658 | 5020 ms |
| 09:50:13.293 | 3058 ms |
| 09:50:13.293 | 5090 ms |
| 09:50:18.207 | 3455 ms |

Widać pary: dwa żądania ruszają razem, jedno wraca po około 3 s, drugie po około 5 s. To ekran i worker. Użytkownik widzi wynik po szybszym z pary, czyli po około 3 s.

Starsze dokończone trafienia tego samego endpointu, 30 dni, 26 żądań z historią `source=db` i `ai_complete=true`: najszybsze 2,3 s, typowo 3,9 s, dziewiąty decyl 6,1 s. Trzy sekundy nie są wypadkiem jednego testu.

`EXPLAIN ANALYZE` na produkcji, wykonanie w samej bazie:

| Zapytanie | Czas | Uwaga |
|---|---:|---|
| wiersz cache `pl>es` / `prado` | 0,07 ms | indeks unikalny, 1 wiersz |
| karty tego profilu (492 żywe) | 0,37 ms | skan tabeli, filtr |
| hasła `lower(lemma)` dla trzech słów | 0,69 ms | skan 715 wierszy `lexical_entries`, przy `prado` 0 trafień |

Baza nie jest zajęta przez 3 sekundy. Trzy sekundy stoją między tymi krokami: proces API czeka na kolejne podróże do bazy, a każda czeka na poprzednią. Łańcuch przed odpowiedzią to co najmniej: użytkownik, profil, wiersz cache, hasła leksykalne, karty, listy, drugi odczyt profilu przy historii, zapis historii, commit z licznikiem.

Odczyt kart nie korzysta z indeksu `(user_id, profile_id, lemma_l2, pos)`, bo pyta o wszystkie karty profilu. Przy 492 wierszach sama baza i tak kończy w ułamku milisekundy. Kosztem jest podróż, nie skan.

### Czego nie wolno zmienić

- Dokończony zapis kończy szukanie. Telefon nie może zacząć dociągania, skoro `ai_complete` jest prawdziwe.
- Niedokończony zapis z propozycjami nadal wraca od razu i nadal każe telefonowi dociągać. Ta gałąź zostaje.
- Brak wiersza albo pusty wiersz bez flagi „dokończone” idzie starą drogą (własny słownik, potem Wikisłownik i mały model). Tego ten punkt nie ruszamy.
- Klucz zostaje dokładnym znormalizowanym wpisem. `prado` i `el prado` pozostają dwoma hasłami. Ściągnięcie rodzajnika zmieniłoby znaczenie szukania i nie jest częścią tej naprawy.
- Propozycje na ekranie mają dalej nieść: hasło, część mowy, tłumaczenie, flagę „dokończone”, informację czy użytkownik już tego się uczy (karta, lista, status) oraz identyfikator hasła leksykalnego, gdy taki istnieje. Od tego zależy chip „już w nauce” i późniejszy zapis karty bez podmiany znaczenia.
- Historia szukania dalej powstaje. Tworzenie karty umie do niej dowiązać kartę w oknie 15 minut. Zapis może powstać tuż po odpowiedzi, nie może zniknąć.
- Licznik użyć wiersza cache dalej rośnie. Może rosnąć po odpowiedzi. Ma być `hit_count = hit_count + 1` w SQL, żeby dwa równoległe żądania się nie nadpisywały.

### Decyzja

Odpowiedź przy trafieniu w zapis czeka tylko na dane, bez których ekran byłby niepełny. Księgowość schodzi za odpowiedź. Drugie, bliźniacze pytanie z telefonu przy gotowej odpowiedzi w ogóle nie startuje.

Ścieżka odpowiedzi, gdy wiersz cache pasuje:

1. Zostaje odczyt użytkownika z tokenu.
2. Zostaje odczyt profilu.
3. Zostaje odczyt jednego wiersza cache.
4. Jedno zapytanie dokłada do tych kilku propozycji karty tego użytkownika i nazwy list. Filtruje po hasłach z propozycji, nie czyta całego profilu „na wszelki wypadek”.
5. Jedno zapytanie dokłada identyfikatory z `lexical_entries` tylko dla haseł, których w zapisie jeszcze nie ma. Przy `prado` identyfikatorów w zapisie nie ma, więc to zapytanie zostaje. Gdy kiedyś zapis będzie je miał wszystkie, tego kroku nie ma.
6. Serwer składa JSON i kończy żądanie.

Po odesłaniu odpowiedzi, w osobnej sesji bazy, bez blokowania telefonu:

- zwiększenie `hit_count`,
- wstawienie `lookup_events` z tymi samymi polami co dziś (`query`, znormalizowany klucz, para, źródło `db`, liczba propozycji, flaga dokończenia, skrócone propozycje, `request_id`).

Telefon:

- `LookupPollWorker` startuje dopiero wtedy, gdy pierwsza odpowiedź nie jest dokończona i sesja naprawdę zaczyna dociąganie.
- Gdy pierwsza odpowiedź jest dokończona, worker się nie kolejkuje. Zostaje jedno żądanie.
- Worker dalej istnieje po to, żeby dokończyć dociąganie, gdy aplikacja zniknie w tle. Tę rolę zachowujemy dla żądania 3, nie dla gotowego zapisu.

Czego ta decyzja nie obiecuje sama z siebie: zejścia do 17 ms. Cztery podróże do bazy jedna po drugiej, przy drodze rzędu setek milisekund, dalej dają ułamek sekundy do około półtorej sekundy. Żeby zejść w okolice dziesiątek milisekund, proces API musi rozmawiać z Postgresem po prywatnej sieci w tym samym regionie. To jest część tej samej naprawy, sprawdzana w kroku poniżej, a nie osobny pomysł na później.

### Instrukcja implementacji

Backend, gałąź trafienia w `LexicalService.lookup_cached`:

- Nie podbijać `hit_count` na obiekcie sesji żądania. Zostawienie tego w sesji zmusza commit odpowiedzi do zapisu licznika.
- Wyciągnąć składanie odpowiedzi tak, żeby przy trafieniu nie wołać pełnego `_annotate_candidates` po wszystkich kartach profilu. Nowe zapytanie: karty żywe tego `user_id` i `profile_id`, których `lemma_l2` pasuje do haseł z propozycji, razem z nazwą listy (`word_lists`) albo z listą systemową, gdy `deck_id` jest puste. Z tego złożyć `in_learning`, `learning_card_id`, `list_id`, `list_name`, `enrichment_status` tak jak dziś.
- Identyfikatory haseł: osobne, krótkie zapytanie po `lang_pair` i hasłach. Nie wybierać kolumny `content`. Dopisać `lexical_entry_id` tylko tam, gdzie da się jednoznacznie złączyć hasło i część mowy, tą samą regułą co `_attach_lexical_ids`.
- Reszta `lookup_cached` (brak wiersza, słownik, Wikisłownik, mały model) zostaje bez zmian zachowania.

Endpoint `lookup_cached` w `backend/app/api/v1/learning.py`:

- Przy trafieniu w zapis nie robić `record_lookup_event` ani `commit` zanim odpowiedź wyjdzie. Jeśli sesja nie ma innych zmian, nie trzeba czekać na commit.
- Historię i licznik odpalić w tle (`BackgroundTasks` albo zadanie na `async_session_factory`), już po zbudowaniu odpowiedzi. Błąd zapisu historii logować i nie zwracać go użytkownikowi. Tak jest też dziś: `record_lookup_event` łyka własny wyjątek.
- Zwiększenie licznika: `UPDATE lookup_query_cache SET hit_count = hit_count + 1, updated_at = now() WHERE id = :id`.

Android, `LookupCoordinator` / `LookupSession`:

- `start` nie woła `enqueueLookup` od razu.
- Kolejkowanie workera przenieść w miejsce, w którym sesja decyduje, że odpowiedź nie jest dokończona i uruchamia dociąganie.
- Przy dokończonej odpowiedzi wołać `cancelLookup`, żeby zaległe zadanie z poprzedniego słowa nie strzeliło drugim pytaniem.

Infra, w tym samym kawałku pracy, zanim uznamy pomiar za wynik:

- Sprawdzić, jakim hostem proces API łączy się z Postgresem. Ma to być adres prywatny Railway w regionie bazy, nie publiczny proxy.
- Na usłudze są dwie repliki, Europa i US. Żądanie obsłużone z repliki po drugiej stronie oceanu względem bazy dalej zapłaci drogę za każdy odczyt. Albo baza i jedyna replika przyjmująca ruch użytkownika są w jednym regionie, albo pomiar z repliki dalekiej opisujemy osobno i nie mieszamy go z wynikiem naprawy.

### Jak sprawdzimy, zanim pójdziemy dalej

Na produkcji, konto `nowy4@test.com`, profil polski → hiszpański, wpisane samo `prado`:

- W `app_logs` jest jedno `POST /api/v1/lookup/cached` na to wpisanie, nie para.
- `duration_ms` tego żądania jest poniżej 800 ms. Jeśli po ścięciu kroków dalej jest powyżej sekundy, zostaje droga do bazy: wracamy do punktu o hoście i regionie, nie dodajemy kolejnych zmian w składaniu odpowiedzi.
- W `lookup_events` w ciągu paru sekund powstaje wiersz: `query=prado`, `source=db`, `ai_complete=true`, `candidate_count=3`.
- Odpowiedź ma trzy propozycje i `ai_complete=true`. Telefon nie woła `POST /api/v1/lookup/expand`.
- W `llm_usage` nie ma nowego wiersza dla tego żądania.
- `hit_count` wiersza `prado` rośnie o 1.
- Na ekranie widać te same trzy propozycje co przed zmianą, z tym samym tłumaczeniem. Jeśli któraś jest już kartą użytkownika, chip nauki zostaje.
- Powtórka z `el prado` nadal nie używa wiersza `prado`. To osobne hasło i tak ma zostać.
