# T-004 · Publiczny serwis aplikacji

**ID:** `E-001/F-007/T-004` · **Status:** `ready` · **Priorytet:** P0 przed zewnętrzną betą.  
**Feature:** [Prywatność i wsparcie](../README.md). **Źródło:** [decyzje z 17.11.2026](../../F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md).

## Uzgodniony rezultat

Osobny publiczny serwis dla aplikacji, zamiast uznawania istniejącej witryny operatora za gotowy serwis produktu. Stabilne adresy HTTPS dla użytkownika, aplikacji i Play; możliwie mały koszt i zakres.

**Dalsze decyzje z 17.11.2026:** przygotować propozycję osobnej domeny aplikacji; konkretna nazwa/rejestrator/koszt nie są jeszcze wybrane. Weryfikacja adresu i ustawienie nowego hasła mają działać także przez prostą stronę WWW na komputerze lub bez instalacji aplikacji. To strony jednorazowych operacji, nie portal konta.

## Minimalny proponowany zakres do zatwierdzenia

- Krótki, uczciwy opis aplikacji/bety, wspieranych platform, ograniczeń i sposobu uzyskania dostępu. Link do closed/internal nie obiecuje dostępu każdej osobie spoza listy.
- Publiczna polityka prywatności, warunki/aviso legal, kontakt/pomoc i żądanie usunięcia konta dostępne bez instalacji lub logowania.
- Zatwierdzona ścieżka usunięcia jest samoobsługowa: dowód hasłem/podłączonym Google lub linkiem na wcześniej zweryfikowany adres, bez instalowania aplikacji; pomoc awaryjnie. Podaje oba etapy 7+7 dni, potwierdza przyjęcie i pozwala cofnąć w terminie; nie wystarcza pusty kontakt.
- Zatwierdzone dokumenty/pomoc PL/EN/ES, wersje/datowanie i dostępność na telefonie. Nie ogranicza to języków nauki ani katalogu 17 locale maili/stron transakcyjnych F-004.
- Uzgodnione URL-e wykorzystywane w Androidzie, mailach i Play; brak sekretów ani danych recenzenta w serwisie/repo.
- Brak opcjonalnego trackingu i banera „na wszelki wypadek”. Faktyczne technologie, zgody i logi według inwentaryzacji danych i decyzji.

## Propozycja domeny i utrzymania — do zatwierdzenia

Właściciel chce inną nazwę niż przedstawione początkowo propozycje i poda ją później. **Żadna konkretna nazwa ani końcówka nie jest wybrana.** Przed zakupem sprawdzić dostępność, zastrzeżenia/premium, cenę i możliwość odnowienia oraz ryzyko pomylenia z innym produktem/prawa do marki; żadnej domeny nie kupiono ani nie zarezerwowano.

Punkt odniesienia cenowego z 17.11.2026: [publiczny cennik .app w Porkbun](https://porkbun.com/tld/app) pokazuje 8,75 USD za pierwszy rok w promocji oraz 14,93 USD za zwykłą rejestrację/odnowienie/transfer. To cena rozszerzenia dla zwykłej nazwy, nie oferta dla powyższego kandydata. Budżet opieramy na odnowieniu, nie samej promocji; końcowa cena, podatki/waluta i warunki wymagają sprawdzenia przy zakupie. .app wymaga działającego HTTPS.

Minimalny proponowany hosting: publiczne strony/formularze w obecnym FastAPI, szablony Jinja2 już są zależnością projektu, osobne od panelu administratora. Własna domena z poprawnym TLS kieruje na właściwy serwis; bez nowego frameworka, CMS i osobnej płatnej usługi tylko do dwóch formularzy. Korzystanie z istniejącego Railway nie gwarantuje zerowego kosztu dodatkowego ruchu — sprawdzić aktualny plan/rozliczenie i zaakceptować przed konfiguracją.

Alternatywa statycznego hostingu pozostaje możliwa, ale nie jest drugim równoległym wdrożeniem. Jeśli wybieramy osobny host WWW/API, trzeba zamknąć CORS, CSP, konfigurację linków i dwa procesy publikacji; nie dokładamy tego bez uzasadnienia.

Zapisany koszt poczty i warunkowo zaakceptowany kierunek Resend Free są w [F-004/T-002](../../F-004-email-i-hasla/tasks/T-002-poczta-i-odzyskiwanie.md#8-dostawca-i-koszty). Przyszła domena jest obsługiwana po jej zakupie i weryfikacji DNS; nie musi istnieć w czasie przygotowania specyfikacji. Transakcyjna wysyłka nie zastępuje zwykłej, monitorowanej skrzynki wsparcia/reply-to.

## Kontrakt stron i linków

Pod ostatecznym `PUBLIC_APP_ORIGIN` przewidzieć:

| Ścieżka | Zawartość / integracja |
|---|---|
| `/` | Opis produktu/bety, wymagania, uczciwa instrukcja dostępu przez Play |
| `/privacy` | Polityka prywatności |
| `/terms` | Warunki korzystania |
| `/legal` | Wymagana informacja o usługodawcy/aviso legal |
| `/support` | Pomoc PL/EN/ES, kopiowalny monitorowany kontakt i cel pierwszej odpowiedzi do 2 dni roboczych |
| `/documents/{kind}/{version}/{locale}` | Niezmienna opublikowana wersja privacy/terms/legal z manifestu; walidowana allowlista, bez dowolnego dostępu do plików |
| `/delete-account` | Rzeczywista ścieżka żądania usunięcia z F-006, nie pozorny formularz |
| `/account/delete-account` | Link dowodu i jawne potwierdzenie żądania; 7 dni na odstąpienie, później do 7 dni na purge |
| `/account/cancel-deletion` | Świeży dowód i cofnięcie w okresie odstąpienia, bez przywracania starych sesji |
| `/account/deletion-status` | Ograniczony stan/terminy z receiptu, bez dostępu do biblioteki i prawa cofnięcia |
| `/account/verify-email` | Formularz jawnego potwierdzenia jednorazowego linku, bez loginu do biblioteki |
| `/account/reset-password` | Formularz ustawienia nowego hasła jednorazowym dowodem |
| `/account/change-email` | Jawne potwierdzenie zmiany/korekty adresu z F-004/T-004, bez loginu WWW |
| `/.well-known/assetlinks.json` | Verified App Links dla uzgodnionego pakietu i faktycznego certyfikatu Play |

Realizację, dowody i API określa [F-006/T-002](../../F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md): forma i terminy zatwierdzone; backupy do około 30 dni i transfery poza EOG dopuszczone warunkowo według [T-001](./T-001-prywatnosc-i-deklaracje.md), rzeczywista konfiguracja/wyjątki nadal wymagają weryfikacji. Jest to rozszerzenie WWW o jednorazowe operacje usunięcia/cofnięcia, nie zwykły login WWW/portal nauki; hasło/Google nie wydają access/refresh. Języki PL/EN/ES są ustalone; teksty prawne wymagają przeglądu, nie ponownego wyboru języków. Nie dodajemy do publicznych stron postępu i panelu administratora.

Formularze wywołują [konkretne API F-004/T-002](../../F-004-email-i-hasla/tasks/T-002-poczta-i-odzyskiwanie.md#3-api-i-odpowiedzi). URL wiadomości ma token we fragmencie, nie w query string. GET nigdy nie potwierdza adresu i nie resetuje hasła; jawny POST, zabezpieczenia nagłówków/CSP, brak śledzenia i zapisu tokena w logach. Każdy stan błędu ma drogę powrotu/pomocy. App Links są ułatwieniem, nie warunkiem wykonania operacji na komputerze.

Wariant z FastAPI publikuje WWW wraz z backendem; nie publikuje przez to nowych ekranów ani obsługi linków Androida. To osobny build/wydanie przez Play. Konfiguracja domeny, prawdziwej poczty i DNS pozostaje osobnym zatwierdzonym działaniem.

## Publikacja, języki i bezpieczeństwo — projekt

- Jeden zestaw wersji dokumentów/manifestu wspólny dla WWW i [legal API T-003](./T-003-warunki-i-informacje-prawne.md). Stabilne `/privacy`/`terms` prowadzą do aktualnej treści, niezmienna ścieżka identyfikuje konkretny opublikowany dokument. Nie podmieniać treści pod zachowanym digest.
- Parametr/wybór języka wyłącznie z allowlisty; dla dokumentów PL/EN/ES jawny selector i oznaczony język. Unsupported locale nie daje pustej strony ani angielskiego tekstu podpisanego jako tłumaczenie. Uzgodnić język z mailem/urządzeniem dla operacji konta według osobnego katalogu F-004.
- Informacje o operatorze i kontakt publikowane po kontrolowanej weryfikacji; nie zbieramy prywatnych danych w taskach. Release weryfikuje kompletność wymaganych wartości, nie pokazuje testerowi placeholderów. Historia dokumentów odpowiada faktycznej opublikowanej treści.
- Brak opcjonalnego trackingu, zewnętrznych fontów/embeds i piksela otwarcia. Nie ładować Google SDK na każdej stronie prawnej; tylko po świadomym uruchomieniu właściwego procesu. Sprawdzić faktyczne storage/cookies i opisać konieczne technologie; brak banera nie jest sam w sobie dowodem zgodności.
- Formularze transakcyjne: TLS, CSP bez niepotrzebnych third-party, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, ochrona przed osadzaniem i właściwe Origin/CORS/CSRF dla użytego mechanizmu. Nie dodawać zwykłej sesji WWW ani automatycznego submit po GET.
- Fragment tokena usunąć z paska przez `history.replaceState` po odczycie do pamięci; nie localStorage ani DOM atrybut/link logowany przez narzędzie. Receipt statusu jako jedyny ograniczony sekret może być w sessionStorage według F-006, nigdy jako dowód cofnięcia. Wyłączenie odczytu storage daje jawny stan i możliwość ponowienia, nie fałszywy sukces.
- Logi reverse proxy/FastAPI/aplikacji według T-001: szablon trasy, bez query/body/fragmentu/tokena i surowych danych formularza, również 404/422/5xx. Operacja nie przenosi hasła/tokena do parametrów URL.
- Po 15 s pojedynczego wywołania formularz ma ponowienie/pomoc, nie bezterminową blokadę. Znaczenie niepewnego wyniku bierze z F-004/F-006; strona nie wysyła nowego żądania usunięcia z nowym ID tylko dlatego, że poprzednie timeoutowało.
- Kontakt pomocy ma kopiowanie i alternatywę bez klienta poczty. Nie tworzymy publicznego formularza dowolnej wysyłki maili; raport bezpieczeństwa treści trafia przez uwierzytelniony endpoint Androida T-002. WWW pozostaje drogą pomocy/praw/usuwania bez aplikacji.
- Testy HTTP/template i przeglądarka: komplet wersji, brak sekretu w logach/referrer/history po odczycie, brak efektu GET/scannera, mobile/desktop/klawiatura/TalkBack. Wyniki na testowym origin i docelowym podpisie App Links przed publikacją.

**Poza zakresem E-001:** sklep, waluta/płatności, portal logowania WWW, marketplace, rozbudowany marketing/CMS i kampanie.

## Zależności i podział odpowiedzialności

- [E-001/F-007/T-001](./T-001-prywatnosc-i-deklaracje.md): polityka prywatności i zgodność danych.
- [E-001/F-007/T-003](./T-003-warunki-i-informacje-prawne.md): treść prawna i zatwierdzenie. Projekt serwisu i przygotowanie treści mogą iść równolegle; przed udostępnieniem testerom muszą być zintegrowane i zweryfikowane.
- [E-001/F-006/T-002](../../F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md): rzeczywista obsługa usunięcia i weryfikacja właściciela.
- [E-001/F-004/T-002](../../F-004-email-i-hasla/tasks/T-002-poczta-i-odzyskiwanie.md): API potwierdzenia/resetu, znaczenie dowodów, stany błędów i dostarczenie wiadomości. W tym tasku jest warstwa publicznych stron, bez duplikacji logiki auth.
- [E-001/F-002/T-002](../../F-002-wydanie-play/tasks/T-002-konfiguracja-play-console.md): odrębna weryfikacja witryny w Console. Nie utożsamiamy hostingu aplikacji WWW z automatycznym potwierdzeniem organizacji.

## Bramki konfiguracji przed publikacją

Języki PL/EN/ES, kanał pomocy i cel 2 dni roboczych są ustalone. Właściciel zatwierdza jeszcze domenę/hosting/koszt i rzeczywisty kontakt/operatora; wykonawca integruje opisany projekt wersjonowania, formularzy i testów z F-004/F-006. Dane wymagane w dokumentach publicznych uzupełniamy bez ujawniania ich w roboczych taskach/czacie.

## Kryteria odbioru

- [ ] Wszystkie wymagane strony dostępne publicznie po HTTPS na stałych adresach, bez konta aplikacji.
- [ ] Treść i linki zgodne w Androidzie, mailach, Play i WWW; dokumenty zatwierdzone i wersjonowane.
- [ ] Żądanie usunięcia działa z telefonu bez aplikacji i trafia do obsługi, z ustalonym potwierdzeniem oraz weryfikacją właściciela.
- [ ] Brak ukrytego trackingu, formularzy zbierających zbędne dane i nieprawdziwych deklaracji produktu.
- [ ] Sprawdzone języki, mały ekran, czytnik ekranu, błędne/nieaktualne adresy oraz monitoring dostępności.
- [ ] Na komputerze bez aplikacji działa weryfikacja i reset; skaner GET niczego nie zużywa, link nie tworzy sesji WWW, token nie wycieka do logów/analityki.
- [ ] Na podpisie Play potwierdzono poprawne App Links i działający fallback WWW; publikacja backendu nie udaje aktualizacji Androida.

**Wynik weryfikacji:** propozycja architektury/mapy stron i sprawdzenie publicznego cennika rozszerzenia; brak implementacji/publikacji. Nie sprawdzono dostępności konkretnych nazw, nie zakupiono domeny i nie zmieniano witryny/DNS.
