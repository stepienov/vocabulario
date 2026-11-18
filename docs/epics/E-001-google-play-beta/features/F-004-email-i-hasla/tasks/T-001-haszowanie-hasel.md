# T-001 · Pełne hashowanie haseł i zgodna migracja

**ID:** `E-001/F-004/T-001` · **Status:** `ready` · **Priorytet / rozmiar:** P0 / M.  
**Feature:** [E-mail i hasła](../README.md). **Źródło:** B-04; potwierdzony F-03 w [analizie](../../../sources/analiza-2026-11-17.md).

## Cel i zakres

Usunąć niejawne obcinanie po 72 bajtach bcrypt. Wybrać współczesny utrzymywany mechanizm hashowania i kontrolowaną obsługę istniejących hashy; nie zmieniać potajemnie interpretacji dawnych długich haseł. Kontrakt UI/API obejmuje całe zaakceptowane hasło, bez trimowania spacji.

**Warunek startu:** [E-001/F-001/T-001](../../F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md); zatwierdzona polityka migracji.

## Zatwierdzona polityka nowych haseł — 17.11.2026

- 15–128 znaków przy rejestracji, resecie, zmianie i dodaniu pierwszego hasła.
- Bez obowiązkowych cyfr, wielkich liter i znaków specjalnych.
- Dozwolone Unicode i spacje; bez automatycznego trimowania i obcinania hasła.
- UI umożliwia wklejanie i używanie menedżerów haseł.
- Dokładny sposób liczenia znaków i wspólne przypadki graniczne Android/API trzeba doprecyzować w kontrakcie technicznym.

## Stan kodu i punkty integracji

- [security.py](../../../../../../backend/app/core/security.py): wspólne `hash_password` / `verify_password` używają `CryptContext` wyłącznie z bcrypt.
- [Schematy](../../../../../../backend/app/schemas/__init__.py): `RegisterRequest` dopuszcza 8–128 znaków; `LoginRequest` nie ma limitu hasła.
- [Auth API](../../../../../../backend/app/api/v1/auth.py): rejestracja i login wywołują synchroniczny hasher bezpośrednio w trasach `async`; nie ma operacji resetu/zmiany/dodania hasła.
- [Zależności](../../../../../../backend/pyproject.toml): `passlib[bcrypt]` i ograniczenie `bcrypt<4.1`; brak Argon2.
- [AuthViewModel](../../../../../../android/app/src/main/java/com/vocabulario/app/ui/auth/AuthViewModel.kt): rejestracja sprawdza `password.length < 8` (jednostki UTF-16), a wspólna walidacja odrzuca `isBlank()`. Wymaga ujednolicenia z API; dozwolone spacje nie mogą być po cichu pomijane.
- [AuthScreen](../../../../../../android/app/src/main/java/com/vocabulario/app/ui/auth/AuthScreen.kt): wspólny formularz logowania/rejestracji, przełączanie widoczności hasła. Zachować istniejący wygląd poza niezbędną walidacją i obsługą menedżerów haseł.

## Proponowany kontrakt techniczny

Poniższe parametry są projektem wykonawcy, nie wynikiem pomiarów ani zgodą na wdrożenie. Plan zasobów/pomiarów jest w F-008, a przejście pakietów w F-002/T-001.

### 1. Walidacja i reprezentacja

- „Znak” oznacza wartość skalarną Unicode, nie bajt, jednostkę UTF-16 ani widoczny grafem. Backend liczy punkty kodowe po odrzuceniu izolowanych surogatów; Android używa liczenia punktów kodowych, nie `String.length`. WWW używa tej samej definicji, nie długości UTF-16.
- Brak NFC/NFKC, case folding, trimowania i innej transformacji przed hashowaniem/weryfikacją. Sekwencja złożona i rozłożona to różne hasła; klient nie może ich zamieniać. UTF-8 całej zaakceptowanej sekwencji jest wejściem Argon2.
- Nowe hasło: 15–128 takich znaków. Login/dowód aktualnego hasła: 1–128; nie stosujemy nowego minimum do weryfikacji starego hasła. Nie odrzucamy hasła wyłącznie przez `isBlank()` — bez osobno zatwierdzonej listy blokowanych haseł byłaby to dodatkowa reguła sprzeczna ze wspólną walidacją.
- Nieprawidłowy Unicode, pusty tekst i przekroczenie limitu odrzucamy przed kosztownym hashowaniem. Nie obcinamy wpisanego/wklejonego tekstu do limitu; formularz pokazuje błąd. Maksimum poprawnej sekwencji UTF-8 wynosi 512 bajtów.
- Jedna walidacja nowego hasła po stronie backendu jest współdzielona przez rejestrację, reset, zmianę i dodanie pierwszego hasła. Oddzielna walidacja dowodu hasła nie stosuje minimum 15. Android/WWW odtwarzają te same zasady dla wygody, ale API jest rozstrzygające.
- Błędy wartości pola: HTTP 422 przez istniejący `api_error`, kody `password_too_short`, `password_too_long`, `password_invalid_unicode`; brak/nieprawidłowy typ pola pozostaje standardowym błędem schematu. Odpowiedź nie zawiera wejściowego hasła. Próg minimum zależy od rodzaju pola, nie od istnienia konta.
- Klienci mapują kody na lokalne komunikaty z limitami 15/128. Istniejące `err_password_short` trzeba zaktualizować we wszystkich 17 locale; dodatkowe klucze również muszą istnieć we wszystkich locale. Rejestracja i ustawianie hasła pokazują regułę przed wysłaniem, login nie sugeruje konieczności posiadania nowego minimum.
- Wklejanie, autofill/menedżer haseł i przełącznik widoczności pozostają dostępne; bez autokorekty i automatycznej zmiany wielkości liter. Pól haseł nie zapisujemy w trwałym stanie, logach, telemetryce ani raportach błędów; nie kopiujemy automatycznie hasła do schowka.

### 2. Hashowanie i zależności

- Propozycja: `argon2-cffi`, `PasswordHasher`, wyłącznie Argon2id v19 dla nowych hashy, jawnie ustawione `memory_cost=19456` KiB (19 MiB), `time_cost=2`, `parallelism=1`, `salt_len=16`, `hash_len=32`, `encoding="utf-8"`. To minimum rekomendowane przez OWASP; nie polegamy na zmiennych domyślnych biblioteki.
- Biblioteka generuje nową kryptograficznie losową sól przy każdym hashowaniu. Przechowujemy pełny ciąg PHC z algorytmem/parametrami/solą/hash w obecnym `User.password_hash`; pole 255 znaków wystarcza dla proponowanego formatu, co trzeba potwierdzić testem. Google-only zachowuje `NULL`.
- Nie dodajemy prehashowania SHA-256, własnego formatu, szyfrowania odwracalnego ani nowego sekretu pepper w tym tasku. Całe zaakceptowane hasło weryfikuje biblioteka.
- `VerifyMismatchError` oznacza niezgodność, nie awarię. Nieznany/uszkodzony format lub inne błędy biblioteki dają kontrolowany błąd operacyjny z repozytoryjnym logowaniem bez hasła/hashu, nigdy pozorny sukces ani automatyczny reset danych. Rozpoznany bcrypt ma osobną obsługę przejścia, nie jest traktowany jak uszkodzony Argon2.
- `check_needs_rehash` sprawdzamy tylko po poprawnym Argon2 verify. Nowy hash aktualizujemy warunkowo względem uprzednio odczytanego hasha i rewizji poświadczeń; równoległy reset/zmiana ma pierwszeństwo. Sam rehash parametrów nie jest zmianą hasła, nie wysyła maila i nie odwołuje sesji. Parametry zapisane w PHC służą do odczytu, nie uruchamiamy przypadkowego downgrade'u przy rollbacku konfiguracji.
- Nową zależność oraz wersję zgodną z docelowym Pythonem i obrazem wybieramy/sprawdzamy podczas implementacji. `passlib`/`bcrypt` usuwamy dopiero po zakończeniu zatwierdzonego przejścia i sprawdzeniu wszystkich ich użyć; nie zostawiamy ich bezterminowo „na wszelki wypadek”.

### 3. Koszt, współbieżność i zapis

- Hash/verify/rehash nie blokują pętli zdarzeń FastAPI. Jedna współdzielona bramka na proces ogranicza równoczesne kosztowne operacje do 2, wykonywanych w wątkach; dotyczy wszystkich tras hasła, również ewentualnego dummy verify i obsługi przejściowej bcrypt. Nie tworzymy osobnego limitera dla każdego żądania.
- Oczekujący na bramkę nie może zajmować blokady wiersza użytkownika ani tokena akcji. Ochrona wejścia i ograniczenie ruchu należą do [T-003](./T-003-odpornosc-auth.md); limity pojedynczego procesu nie zastępują wspólnego ograniczenia ruchu między replikami.
- Nowy hash przygotowujemy przed sekcją blokującą; uprawnienia, rewizje, ważność jednorazowego dowodu oraz stan konta sprawdzamy ponownie we właściwej transakcji. Reset/zmiana/dodanie hasła i skutki dla sesji są atomowe według [T-002](./T-002-poczta-i-odzyskiwanie.md) i [kontraktu sesji](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md). Funkcja hashowania nie robi commit.
- Przed wdrożeniem implementacji trzeba zmierzyć na izolowanym środowisku o takich samych zasobach jak planowane Railway: p95 pojedynczego hash/verify bez kolejki nie większe niż 500 ms (minimum 100 próbek po rozgrzaniu), RSS i responsywność przy 2 równoczesnych operacjach na proces oraz docelowej liczbie procesów/replik. Łączny szczyt RSS ma pozostawać poniżej 80% przyznanej pamięci, bez OOM/restartów i swapowania.
- Niespełnienie progów wymaga zmiany planu zasobów/limitu współbieżności lub ponownego uzgodnienia parametrów; nie obniżamy zabezpieczeń poniżej podanego minimum ani nie zatwierdzamy dodatkowych kosztów automatycznie. Bez pomiarów nie uznajemy wartości za zweryfikowane.

## Obecne konta i dane przed betą

Właściciel nie wymaga rozbudowanej automatycznej migracji haseł i chce ciągłości kont/postępu. Proponowana prosta procedura wykonawcza: **zachować User.id i ustanowić nowe hasło przez reset T-002**, zamiast tworzyć zastępcze konta/przepisywać karty. Nie oznacza to zgody na operację danych teraz. Wcześniejsze rozważanie nowych kont nie jest planowanym resetem prawdziwej bety.

1. Na syntetycznej starej bazie potwierdzić ID/profile/SRS/historię, kopię/restore i odzyskanie przez aktualną skrzynkę lub podłączone Google; przed przełączeniem znanych instalacji uzgodnić outbox według [F-002/T-001](../../F-002-wydanie-play/tasks/T-001-release-i-aktualizacja.md).
2. Przed odcięciem starego protokołu powiadomić obecne osoby i sprawdzić, że istnieje używalna ścieżka dowodu. Niewłaściwa/niedostępna skrzynka bez innego wiarygodnego dowodu = zachowany recovery/wsparcie, nie automatyczna zmiana adresu lub nowe puste konto.
3. Nowy backend rozpoznaje format bcrypt, ale **nie uznaje go za weryfikację całego hasła i nie rehashuje po loginie**. Hasłowy login takiego konta ma ten sam neutralny 401/dummy work co inne nieprawidłowe dane, z zawsze dostępnym resetem. Instrukcja migracji wprost mówi, że przed pierwszym hasłowym loginem potrzebne jest ustanowienie nowego hasła.
4. Reset do bieżącej skrzynki/revision zapisuje Argon2, weryfikuje tylko właściwy adres, zwiększa rewizję i odwołuje wszystkie sesje. ID/dane pozostają, potem nowy login. Już podłączone Google może logować do tego samego ID po swoich normalnych dowodach; nie pozwala nadpisać istniejącego hasła jako „dodanie pierwszego”.
5. `/me` dodaje po uwierzytelnieniu `password_upgrade_required` wynikające z rozpoznanego legacy formatu; publiczny login nie ujawnia rodzaju konta. Ekran konta zamiast zmiany wymagającej starego bcrypt prowadzi do resetu. Google-only ma `false`.
6. W runtime nowego release brak weryfikatora bcrypt. Po wdrożeniu/uzgodnieniu przejścia usunąć `passlib[bcrypt]` i pin `bcrypt<4.1`, jeśli brak innych prawdziwych użyć. Rozpoznanie prefiksu legacy pozostaje do jawnego kierowania do resetu; nieznany/uszkodzony format nadal jest kontrolowanym błędem operacyjnym.

Nie da się uzyskać Argon2 z bcrypt bez nowego dowodu/hasła; nie przeliczamy hasha jako hasła ani nie zgadujemy długości oryginału. Nie zostawiamy czasowo dozwolonego bcrypt loginu bez terminu ani nie akceptujemy równoważnych pierwszych 72 bajtów. Rollback zachowuje User.id i nowy kontrakt auth, nie przywraca starego weryfikatora. Faktycznie nieodzyskiwalny przypadek pozostaje BLOCKED/wsparcie z zachowaną pracą.

## Testy implementacji i dowody

- Wspólny zestaw przypadków Android/API/WWW: 14/15/128/129 znaków; znaki spoza BMP, łączone i rozłożone, spacje na brzegach i w środku, same spacje oraz izolowane surogaty. Przykład rozróżniający UTF-16: 14 liter ASCII + jeden znak spoza BMP to 15, nie 16 znaków.
- Poprawna rejestracja/login i ustawianie hasła na każdej z czterech tras; błędna walidacja nie tworzy konta, nie zużywa tokena resetu, nie zmienia hash/revisions/sesji. API bez Androida także egzekwuje reguły.
- Dwa hasła mające wspólne pierwsze 72 bajty, ale inny dalszy ciąg, nie mogą wzajemnie przejść Argon2 verify. Pokryć także przekroczenie tej granicy przez Unicode, bez zmiany zaakceptowanego tekstu.
- Poprawne/błędne hasło, uszkodzony/nieznany hash, Google-only, rozpoznany bcrypt i zasady wybranej ścieżki przejścia. Nie wymagamy przebudowy wszystkich testów auth ani testowania wnętrza biblioteki.
- Równoległy rehash i reset/zmiana hasła nie przywracają starego poświadczenia ani odwołanej sesji; rollback nie zostawia częściowego zapisu. Test z izolowanym PostgreSQL według istniejących zasad testów projektu.
- Test API błędnej walidacji potwierdza brak hasła w odpowiedzi. Syntetyczny charakterystyczny tekst pozwala sprawdzić brak ujawnienia w przechwyconych logach/raportach także na ścieżkach wyjątków; uwzględnić standardowe błędy Pydantic zawierające `input`.
- Testy UI: walidacja pola, wklejanie, widoczność, menedżer haseł, czytnik ekranu i duży tekst. Zmiany napisów sprawdza istniejący `scripts/check_ui_strings.py`; pełna walidacja repo to `python scripts/ci_check.py`. Benchmark nie jest testem CI opartym na szybkości maszyny runnera.

## Bramka odbioru implementacji

- [ ] Zatwierdzona definicja znaku i brak normalizacji; kontrakt walidacji i błędów spójny z klientem WWW i T-003, bez odbijania hasła w odpowiedziach/logach.
- [ ] Zweryfikowany wybór biblioteki/wersji, format zapisu, jawne parametry oraz zatwierdzone progi i plan pomiarów pamięci/czasu na docelowych zasobach; mechanizm ograniczenia współbieżności bez blokowania event loop. Wyniki pomiarów są warunkiem odbioru implementacji.
- [ ] Próba ścieżki resetu z zachowaniem ID, kolejności F-002 i usunięcia weryfikatora bcrypt, bez utraty danych/outboxu; publiczny błąd nadal neutralny.
- [ ] Powiązane kontrakty resetu/zmiany/dodania hasła oraz recent-auth domknięte; brak obchodzenia zatwierdzonych reguł sesji.
- [ ] Zaplanowane testy mają wskazane miejsca w implementacji; wykonane testy/pomiary będą warunkiem ukończenia implementacji, nie są deklarowane jako zaliczone przez ten dokument.

### Źródła techniczne

- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) — Argon2id, minimum parametrów i granica bcrypt.
- [argon2-cffi — how-to](https://argon2-cffi.readthedocs.io/en/stable/howto.html) — verify, rehash i koszt pamięci domyślnych ustawień.

## Kryteria i weryfikacja

- [ ] Dwa różne obsługiwane hasła nie weryfikują się jako jednakowe wskutek obcięcia.
- [ ] A-03: granice bajtów/znaków, Unicode, spacje i UI/API.
- [ ] Istniejące konta bcrypt mają sprawdzoną ścieżkę dostępu i migracji.
- [ ] Testy nowych i starych hashy, w tym dawnych długich haseł; brak realnych haseł w fixture/logach.

**Poza zakresem:** implementacja resetu pocztą (T-002), publiczny transfer danych i zmiana całego dostawcy auth. **Wynik weryfikacji:** przegląd kodu/dokumentacji i kompletny projekt z migracją; bez implementacji, benchmarków, testów runtime i operacji na produkcji.
