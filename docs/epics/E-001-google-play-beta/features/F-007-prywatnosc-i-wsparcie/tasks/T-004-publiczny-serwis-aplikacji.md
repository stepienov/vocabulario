# T-004 · Publiczny serwis aplikacji

**ID:** `E-001/F-007/T-004` · **Status:** `in_progress` · **Priorytet:** P0 przed zewnętrzną betą.  
**Feature:** [Prywatność i wsparcie](../README.md). **Źródło:** [decyzje z 17.11.2026](../../F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md).

## Koncepcja i plan serwisu — 22.11.2026

**Stan:** na zlecenie właściciela zaimplementowano stronę w kierunku **A · Centralny / D · Magazyn**, z lokalnym logo i fontami aplikacji, tekstami PL/EN/ES oraz poprawioną pomocą. Treści są robocze, bez obietnicy dostępnej instalacji; dokumenty prawne zachowują dotychczasowe wersje i wymagają przeglądu. Publikacja i rzeczywiste przepływy wymagają osobnego potwierdzenia po wdrożeniu. Starsze fragmenty o niewybranej domenie i zmianie e-maila są historyczne.

### Stan wyjściowy

- Działa domena `vocabulario.io`; publiczne strony obsługuje istniejący backend FastAPI. Wdrożenie backendu i wydanie Androida to oddzielne czynności.
- 22.11.2026 sprawdzono publicznie `/` i `/support`: strona główna zawiera krótki opis i linki; pomoc błędnie obiecuje zmianę adresu e-mail. Strony prawne w poprzednim sprawdzeniu miały oznaczenie wersji roboczej. Dostępność URL ani kod formularza nie potwierdzają przejścia całej operacji.
- Kod zawiera trasy strony głównej, dokumentów, pomocy i jednorazowych operacji konta. Stan konfiguracji, dostępność poszczególnych metod i ich działanie end-to-end trzeba sprawdzić w izolowanym środowisku, a później bezpiecznie na docelowym wydaniu. Nie zakładać, że funkcja usuwania jest włączona na produkcji.
- [Zmiana adresu e-mail została wycofana](../../F-004-email-i-hasla/tasks/T-004-zmiana-emaila.md): nie projektować jej ekranu ani nie reklamować tej funkcji. Starsze opisy w tym zadaniu i indeksach nie odzwierciedlają tej decyzji.

### Kierunek wizualny

- **A · Centralny:** wyśrodkowany, czytelny pierwszy ekran, jeden główny komunikat i uporządkowany rząd informacji o funkcjach.
- **D · Magazyn:** większa typografia, więcej oddechu i wyraźne poziome sekcje, prosta opowieść „znajdź → zapisz → powtarzaj”.
- **Połączenie do zaprojektowania:** autentyczne logo na górze; centralnie ustawiony nagłówek i krótki opis; poniżej przestronna, redakcyjna sekcja przedstawiająca funkcje i/lub rzeczywisty interfejs. Spokojny, nowoczesny charakter, bez krzykliwego marketingu i przeładowania. To propozycja, nie zatwierdzona makieta końcowa.
- **Paleta wybranej makiety pastelowej:** tło `#F8F6FC`, lawenda `#E3DDF8`, mięta `#DCEFE9`, brzoskwinia `#FFEADF`, akcent nagłówków `#6964BE`. Dopasować elementy do aplikacji: podstawowy przycisk `#5F6ABE`, tekst `#2D3039`, jasne karty `#FFFEFA`, pola/kafelki `#E7EAEE`, tło aplikacji `#F1F5F4`. Zastosowanie i kontrast sprawdzić na ekranie; nie zmieniać motywu aplikacji w ramach tego taska.
- Używać rzeczywistego logo i kroju Inter z aplikacji oraz podobnych zaokrąglonych przycisków, pól i etykiet. Logo i zasoby powinny być hostowane lokalnie; przed dystrybucją sprawdzić prawa do używanych materiałów i fontów. Pokazane w makietach karty są symulacją, nie zrzutami ekranu.
- Strony treści i formularze zachowują wspólną identyfikację, ale stawiają czytelność i wykonanie zadania ponad dekoracje. Wersja mobilna to pełny układ, nie pomniejszony desktop.

### Mapa stron i podstron

Wiersze opisują **docelowy zakres oraz weryfikację**, a nie twierdzenie, że wszystkie funkcje są już gotowe. Aktualne ścieżki pozostają stabilne dla aplikacji, e-maili i Play; decyzję o nowych adresach podejmujemy wyłącznie, gdy jest potrzebna.

| Adres / miejsce | Przeznaczenie i zakres |
|---|---|
| `/` | Strona główna: czym jest aplikacja, Android, uczciwa informacja o zamkniętej becie i dostępie dla zaproszonych; najważniejsze funkcje i droga do pomocy/dokumentów. Na razie bez fikcyjnego przycisku instalacji albo zapisów. Po przygotowaniu wydania można dodać właściwą instrukcję i link Play dla uprawnionych osób. |
| Sekcje `/` | Pierwszy ekran, krótka prezentacja „wyszukaj → zapisz na listę → ćwicz i powtarzaj”, przykładowy lub prawdziwy ekran aplikacji, informacja o becie, stopka. Nie trzeba tworzyć osobnych URL dla każdej sekcji. |
| `/support` | Kontakt, podstawowa pomoc dla konta/hasła, wskazanie zgłoszenia błędnej treści w aplikacji, bezpieczna ścieżka usunięcia konta, realny czas odpowiedzi. Poprawić błędny opis zmiany e-maila; nie prosić o hasła lub jednorazowe linki. Sprawdzić faktyczny odbiór poczty. |
| `/privacy` | Aktualna polityka: faktyczne dane, cele, dostawcy, prawa, retencja i usuwanie; link do informacji o usługodawcy i kontaktu. Przegląd prawny i zgodność z realną konfiguracją przed publikacją jako finalnej. |
| `/terms` | Aktualne warunki korzystania z usługi i bety, wymagania konta, ograniczenia i zasady treści; osobny przegląd i akceptacja prawna. |
| `/legal` i `/documents/{kind}/{version}/{locale}` | Indeks informacji prawnych i usługodawcy oraz niezmienne wersje dokumentów z datą/językiem. Nie podmieniać zatwierdzonej wersji pod dotychczasowym identyfikatorem lub digestem. |
| `/delete-account` | Dostępna bez instalacji ścieżka rozpoczęcia rzeczywistego usunięcia konta z weryfikacją właściciela. Jasno opisać zakres danych, 7 dni na cofnięcie, maksymalnie kolejne 7 dni do usunięcia danych aktywnych i zweryfikowane wyjątki dla kopii. Kontakt jest pomocą awaryjną, nie atrapą procedury. |
| `/account/delete-account` | Jednorazowy dowód i jawne potwierdzenie żądania; bez automatycznego usuwania po otwarciu linku. |
| `/account/cancel-deletion` | Potwierdzenie cofnięcia na podstawie właściwego świeżego dowodu i w terminie; nie przywraca automatycznie starych sesji. |
| `/account/deletion-status` | Ograniczony stan i terminy procesu na podstawie uprawnionego dowodu/receiptu; brak dostępu do biblioteki i brak prawa do cofnięcia z samego receiptu. |
| `/account/verify-email` | Jednorazowy link i jawne potwierdzenie adresu; czytelne stany poprawnego, użytego, wygasłego i błędnego linku oraz droga do ponowienia/pomocy. |
| `/account/reset-password` | Jednorazowy link i bezpieczne ustawienie nowego hasła; jasne wymagania, błędy, sukces, wygasły link i droga do ponowienia/pomocy. |
| `/.well-known/assetlinks.json` | Techniczny plik Android App Links, nie podstrona wizualna. Uzupełnić właściwy pakiet i SHA-256 certyfikatu Play oraz sprawdzić działanie z wydaniem Play; WWW nadal ma działać jako fallback. |
| Stany błędu | Czytelne strony lub komunikaty 404, niedostępności, utraty sieci, timeoutu i błędów operacji, z drogą do powrotu lub pomocy; bez fałszywego potwierdzenia sukcesu. |

Stała nawigacja i stopka powinny zapewnić dostęp do strony głównej, pomocy, polityki prywatności, warunków, informacji prawnych i usuwania konta. Operacje jednorazowe nie są ogólnym portalem logowania ani biblioteką WWW. Nie tworzyć `/account/change-email` ani strony zmiany adresu.

### Treść, języki i bezpieczeństwo

- Opisać tylko istniejące możliwości i rzeczywiste ograniczenia. Nie deklarować dostępności w Play, nieograniczonych zapisów, ceny, skuteczności nauki ani funkcji, których nie potwierdzono. Informację o sposobie dostępu do bety uzgodnić przed publikacją.
- Publiczne strony i dokumenty: PL/EN/ES, jawny wybór języka i zrozumiały fallback. Strony transakcyjne i e-maile zachowują **17 istniejących locale**, w tym kierunek RTL; nie ograniczać ich do trzech języków.
- Zachować bezpieczeństwo i kontrakty formularzy opisane poniżej oraz w F-004/F-006: jawna akcja POST zamiast skutków GET, token we fragmencie i poza logami/historią, odpowiednie CSP, brak śledzenia, odpowiednie ograniczenie dostępu oraz rzeczywiste stany timeoutu i ponowienia.
- Unikać zbędnych danych, zewnętrznych fontów, trackerów i nowych usług. Google ładować tylko tam, gdzie jest potrzebne i użytkownik wybierze tę metodę; faktyczne cookies/storage i obowiązki zweryfikować.
- Dokumenty prawne, kontakt, dostawców, okresy przechowywania, procedurę usuwania i deklaracje Play zweryfikować względem rzeczywistej usługi; zatwierdzenie prawne należy do uprawnionej osoby, nie wynika z ukończenia projektu graficznego.

### Historyczna kolejność planu

1. Uzgodnić ostateczną kompozycję A/D, komunikat główny, treści, elementy interfejsu i sposób przedstawienia bety. Przygotować lub zaakceptować realne zrzuty bez danych użytkowników, jeżeli będą potrzebne.
2. Sprawdzić obecne trasy i powiązania Android/e-mail/Play; zachować istniejące adresy, bezpieczeństwo operacji i kompatybilność. Ustalić faktyczne blokady i funkcje, nie opierać prac wyłącznie na starszym opisie taska.
3. W istniejącym serwisie wdrożyć uzgodniony wspólny wygląd, stronę główną i poprawną pomoc; następnie podstrony informacyjne i operacyjne bez zmiany ich kontraktów. Dodać tłumaczenia dla właściwych katalogów językowych.
4. Przetestować linki, widoki i działanie formularzy na izolowanym środowisku, bez niszczenia kont produkcyjnych; porównać opisy z faktycznym zachowaniem i zatwierdzonymi dokumentami.
5. Osobno uzgodnić publikację i konfigurację, w tym kontakt i App Links; po wdrożeniu sprawdzić HTTPS, adresy i bezpieczne scenariusze. Operacje na produkcji i Play wymagają odpowiednich uprawnień i osobnego zlecenia.

### Odbiór projektu i późniejszej realizacji

- [ ] Właściciel zatwierdził konkretny układ, treść, dostęp do bety oraz reprezentację ekranu aplikacji.
- [ ] Wszystkie strony z mapy mają kompletne treści i właściwe stany; linki w WWW, aplikacji, mailach i Play prowadzą we właściwe miejsca.
- [ ] Sprawdzone desktop i telefon, małe szerokości, duży tekst, klawiatura/czytnik, kontrast, PL/EN/ES i istniejące locale stron transakcyjnych.
- [ ] Automatyczne testy oraz bezpieczne próby end-to-end potwierdzają sukces, wygaśnięcie, błędy, ponowienie i ochronę danych dla operacji konta; GET/skaner nie wykonuje operacji.
- [ ] Prawnik/właściciel zatwierdził właściwe dokumenty i deklaracje; pomoc i procedura usuwania faktycznie działają, a terminy odpowiadają konfiguracji.
- [ ] App Links, link Play i wydanie Androida potwierdzone na docelowym podpisie; osobno zapisane, co wdrożono i gdzie.

**Dowód etapu implementacji:** szablony i zasoby `backend/app/public_web/`, testy `backend/tests/test_public_site.py` i `test_public_web.py`. Nie są dowodem przeglądu prawnego ani testu rzeczywistego Google.

---

## Uzgodniony rezultat

Osobny publiczny serwis dla aplikacji, zamiast uznawania istniejącej witryny operatora za gotowy serwis produktu. Stabilne adresy HTTPS dla użytkownika, aplikacji i Play; możliwie mały koszt i zakres.

**Historyczna decyzja z 17.11.2026:** przygotować propozycję osobnej domeny aplikacji. Aktualnie używana jest `vocabulario.io`. Weryfikacja adresu i ustawienie nowego hasła mają działać także przez prostą stronę WWW na komputerze lub bez instalacji aplikacji. To strony jednorazowych operacji, nie portal konta.

## Minimalny proponowany zakres do zatwierdzenia

- Krótki, uczciwy opis aplikacji/bety, wspieranych platform, ograniczeń i sposobu uzyskania dostępu. Link do closed/internal nie obiecuje dostępu każdej osobie spoza listy.
- Publiczna polityka prywatności, warunki/aviso legal, kontakt/pomoc i żądanie usunięcia konta dostępne bez instalacji lub logowania.
- Zatwierdzona ścieżka usunięcia jest samoobsługowa: dowód hasłem/podłączonym Google lub linkiem na wcześniej zweryfikowany adres, bez instalowania aplikacji; pomoc awaryjnie. Podaje oba etapy 7+7 dni, potwierdza przyjęcie i pozwala cofnąć w terminie; nie wystarcza pusty kontakt.
- Zatwierdzone dokumenty/pomoc PL/EN/ES, wersje/datowanie i dostępność na telefonie. Nie ogranicza to języków nauki ani katalogu 17 locale maili/stron transakcyjnych F-004.
- Uzgodnione URL-e wykorzystywane w Androidzie, mailach i Play; brak sekretów ani danych recenzenta w serwisie/repo.
- Brak opcjonalnego trackingu i banera „na wszelki wypadek”. Faktyczne technologie, zgody i logi według inwentaryzacji danych i decyzji.

## Historyczna propozycja domeny i utrzymania

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

Języki PL/EN/ES, kanał pomocy i cel 2 dni roboczych są ustalone. Domena `vocabulario.io` działa; przed publikacją należy potwierdzić koszt/utrzymanie, rzeczywisty kontakt/operatora i działanie formularzy. Wykonawca integruje wersjonowanie, formularze i testy z F-004/F-006. Dane wymagane w dokumentach publicznych uzupełniamy bez ujawniania ich w roboczych taskach/czacie.

## Kryteria odbioru

- [ ] Wszystkie wymagane strony dostępne publicznie po HTTPS na stałych adresach, bez konta aplikacji.
- [ ] Treść i linki zgodne w Androidzie, mailach, Play i WWW; dokumenty zatwierdzone i wersjonowane.
- [ ] Żądanie usunięcia działa z telefonu bez aplikacji i trafia do obsługi, z ustalonym potwierdzeniem oraz weryfikacją właściciela.
- [ ] Brak ukrytego trackingu, formularzy zbierających zbędne dane i nieprawdziwych deklaracji produktu.
- [ ] Sprawdzone języki, mały ekran, czytnik ekranu, błędne/nieaktualne adresy oraz monitoring dostępności.
- [ ] Na komputerze bez aplikacji działa weryfikacja i reset; skaner GET niczego nie zużywa, link nie tworzy sesji WWW, token nie wycieka do logów/analityki.
- [ ] Na podpisie Play potwierdzono poprawne App Links i działający fallback WWW; publikacja backendu nie udaje aktualizacji Androida.

**Historyczny wynik weryfikacji z etapu propozycji:** sprawdzono architekturę/mapę stron i publiczny cennik rozszerzenia; ówczesne informacje o braku domeny i publikacji nie opisują aktualnego stanu.

**Aktualny postęp:** trasy i szablony stron informacyjnych oraz jednorazowych operacji są w backendzie. Rozróżnienie implementacji, konfiguracji i weryfikacji oraz nowy plan strony podano na początku zadania.
