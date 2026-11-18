# T-003 · Warunki bety i informacje prawne

**ID:** `E-001/F-007/T-003` · **Status:** `ready` · **Priorytet:** P0 przed pierwszą zewnętrzną betą.  
**Feature:** [Prywatność i wsparcie](../README.md). **Źródło:** [decyzje startowe](../../F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md).

## Cel i rozróżnienie obowiązków

Przygotować adekwatne dokumenty dla rzeczywistej usługi, nie kopiować regulaminu innej aplikacji i nie uznawać małej bety za zwolnienie z ochrony danych.

| Materiał | Rola / podstawa do weryfikacji |
|---|---|
| Polityka prywatności i informacja przed pozyskaniem danych | Obowiązek informacyjny RGPD/GDPR i wymagania Play; właściciel: T-001 |
| Informacje o usługodawcy / aviso legal | Obowiązek identyfikacyjny usługodawcy objętego LSSI, w szczególności art. 10; sprawdzić właściwy zakres informacji |
| Warunki korzystania / condiciones de uso bety | Uzgodniony opis relacji z użytkownikiem, zasad konta/AI/wsparcia i ograniczeń bety; zakres obowiązkowych postanowień potwierdza przegląd prawny, nie twierdzimy, że każda aplikacja musi mieć dokument dokładnie o takiej nazwie |
| Publiczna ścieżka usunięcia | Wymaganie Play dla tworzenia kont w aplikacji; realizacja w E-001/F-006/T-002, nie sam link bez obsługi |
| Cookies / technologie urządzenia | Informacja i ewentualna zgoda zależnie od rzeczywistej konfiguracji oraz wyjątków; inwentaryzacja w T-001 |

Warunki i informacje mogą być logicznymi sekcjami wspólnego serwisu WWW, nie wymagają budowy rozbudowanego portalu. Publiczny serwis aplikacji ma osobny zakres w [E-001/F-007/T-004](./T-004-publiczny-serwis-aplikacji.md); tutaj ustalamy treść, obowiązki, wersjonowanie i reguły akceptacji. Dane identyfikacyjne operatora wypełniamy i weryfikujemy w odpowiednim procesie publikacji; **nie zbieramy numerów podatkowych, prywatnych adresów ani kont testerów w specyfikacji publicznego repo**. Dokument publiczny musi jednak ujawniać informacje wymagane prawem — samo ukrycie ich w Git nie znosi obowiązku.

## Uzgodniony zakres i treść

- Dorośli, proste oświadczenie pełnoletności bez daty urodzenia/dokumentu; dokumenty/pomoc PL/EN/ES zatwierdzone 17.11.2026. Kraje Play, wymagane dane operatora/kontakt i osoba zatwierdzająca prawo pozostają bramką publikacji.
- Dostępność i czas trwania bety, wymagania konta, zasady dozwolonego użycia/importowania treści i koszty, jeśli występują. Nie zakładać przyszłej bezpłatności wszystkich funkcji ani zatwierdzonej waluty.
- Treści AI mogą być błędne; opisać zgłoszenia i ograniczenia bez niezgodnego z prawem wyłączenia odpowiedzialności lub praw konsumenta.
- Zmiana/zakończenie usługi, konta i dostęp do danych: zgodność z rzeczywistym procesem usunięcia, retencją i umówionym losem danych po becie. Bez obietnic eksportu, którego produkt nie dostarcza; obsługa praw użytkownika pozostaje do zapewnienia.
- Punkty wejścia w Androidzie: przed rejestracją e-mail/Google, ekran weryfikacji i ustawienia. Ustalić osobno akceptację warunków oraz informowanie o prywatności; nie zastępować obu zbiorczą zgodą.
- Właściciel zatwierdził osobną akceptację warunków i jednorazowe potwierdzenie dla istniejących kont przy przejściu do bety. Wersjonowanie i reguły poniżej są projektem wykonawczym.
- Hosting publicznych stron HTTPS, dostęp bez logowania, stabilne adresy dla Play i aplikacji, zachowanie przy braku sieci.

## Mechanizm wersji i akceptacji — projekt

### Dokumenty i dowód

Jeden manifest publikowanych wersji po stronie backendu/WWW: `terms_version`, `privacy_version`, data publikacji/obowiązywania, język, URL niezmiennej wersji i digest treści. Wersja warunków identyfikuje uzgodniony komplet PL/EN/ES, nie trzy różne umowy. Zmiana tekstu aktualizuje wersję; nie podmieniać historii pod tym samym digest. Zmiana tylko literówki może nie wymagać ponownej akceptacji, lecz nadal ma nową opublikowaną rewizję i udokumentowaną klasyfikację.

Minimalny dowód przy User.id: zaakceptowana wersja warunków i locale, czas serwera, wersja treści oświadczenia pełnoletności i czas potwierdzenia. Bez daty urodzenia, skanu, raw IP, fingerprintu, hasła i Google tokena. Historia wersji publicznych nie jest historią osób. Retencja osobowego dowodu zgodnie z T-001/F-006; ewentualny obowiązek zachowania dłużej musi być konkretnie oceniony przed publikacją.

Warunki, prywatność i informacja o AI są rozróżnione:

- Niezaznaczone oświadczenie „Mam co najmniej 18 lat” i osobna niezaznaczona akceptacja warunków z linkiem. Brak akceptacji nie tworzy konta automatycznie.
- Dostępny link i krótka informacja o prywatności, bez „zgadzam się na politykę prywatności”. Nie oznaczać odczytu strony jako zgody; nie wymagać scrollowania do końca dla samego dowodu.
- Informacja o przesyłaniu treści do AI przed pierwszym takim przepływem; T-001 określa dodatkowy wyróżniony komunikat/zgodę tam, gdzie wynika to z analizy faktycznego przetwarzania. Zgoda marketingowa/analityczna nie jest częścią tego zakresu.

### API i rejestracja

| Operacja | Proponowany kontrakt |
|---|---|
| `GET /api/v1/legal/current?locale=...` | Publiczny manifest: wersje/daty/URL/digest oraz wskazany faktyczny język dokumentu. Bez danych konta; obsługuje ETag. Backend zwraca dostępne PL/EN/ES, nie udaje tłumaczenia na inne locale |
| Rejestracja e-mail / Google tworzące konto | Rozszerzenie żądania o `legal_acceptance: {terms_version, locale, adult_confirmed:true}`; wersja i locale zweryfikowane na serwerze, czas tylko serwerowy. Zapis dowodu i User w tej samej transakcji |
| `GET /me` | Addytywne `legal_status: {accepted_terms_version, required_terms_version, adult_confirmed, acceptance_required}`; bez prywatnej historii i sekretów |
| `POST /api/v1/me/legal-acceptance` | Bieżąca sesja i jawnie przesłany komplet jak wyżej; 200 z aktualnym legal_status po commit. Ten sam komplet idempotentny, nie przesuwa pierwotnego czasu. Inna nowsza akceptacja wymaga jawnej akcji |

Nieprawidłowa/nieaktualna wersja w submit →409 `legal_version_changed` z aktualnym manifestem, bez utworzenia konta/automatycznej akceptacji nowej treści. Brak wymaganego potwierdzenia →422 bez odbijania sekretów. Walidacja wymogów przed efektem tworzenia konta; Google nie zużywa dowodu do utworzenia częściowego User przed wykryciem braku warunków. Nie zmieniać reguł linkowania istniejącego konta po sub.

Akceptacja online; offline można odczytać ostatnią zapisaną wersję/stan, ale nie pokazywać nowego potwierdzenia jako przyjętego przez serwer. Cache manifestu nie oznacza, że wersja nadal obowiązuje przy submit. Podwójny tap, utrata odpowiedzi i retry nie tworzą kolejnego konta lub fałszywej nowej zgody. Warunki dostępne przed otwarciem wyboru Google/rejestracją i w ustawieniach; nie pytać istniejącego zaakceptowanego użytkownika przy każdym loginie.

### Istniejące konta, istotna zmiana i odmowa

Stare konta nie dostają „zaakceptowano” migracją bez dowodu. Po prawidłowym loginie brak wymaganej akceptacji daje ograniczony stan, nie `invalid_credentials`; **403 `terms_acceptance_required`** dotyczy chronionych operacji nauki/sync. Sesja/właściciel i praca lokalna pozostają, bez zerowania outboxu.

Osobny legal gate, a nie przywracanie odwołanej sesji: dozwolone `/me`, manifest/akceptacja, wymagane potwierdzenie adresu, odzyskanie dostępu/logout, pomoc/prawa i usunięcie konta zgodnie z własnym dowodem F-006. Lifecycle usuwania i brak ważnej sesji mają pierwszeństwo. Akceptacja nie weryfikuje e-maila ani nie cofa usuwania. Po bramce wymaganej weryfikacji/warunków normalna praca dopiero przy spełnieniu obu.

Android zapamiętuje stan przy właścicielu; pierwszy brak potwierdzenia/serwerowe wymaganie blokuje naukę do akceptacji, ale nie kasuje cache. Dotychczas zaakceptowana instalacja nie odkrywa istotnej zmiany, będąc offline: nie obiecujemy zdalnej natychmiastowej blokady, nie dodajemy pollingu. Po otrzymaniu aktualnego wymagania legal gate obejmuje też offline; kontrola owner+generation chroni opóźnione odpowiedzi. Niedostępny manifest daje retry/pomoc, nie domyślne zaakceptowanie.

Istotna zmiana: publikacja nowej czytelnej wersji i streszczenia zmian, ustalony termin, ocena prawna potrzeby ponownej akceptacji/innej zgody; backend egzekwuje dopiero wymagany zestaw, nie dowolny numer klienta. Odmowa nie usuwa automatycznie konta ani nie wyraża zgody; pozostają pomoc/prawa/logout/usunięcie. Brak sieci nie jest odmową.

## Treść i prawa do materiałów

Dokumenty opisują rzeczywiste samodzielne konto, weryfikację, metody Google/hasło, prywatne profile/naukę, lokalne przypomnienia, bezpłatną betę bez płatności, niedoskonałość AI i zgłoszenia. Cel odpowiedzi 2 dni robocze, usuwanie 7+7, kopie do około 30 dni i zewnętrzni odbiorcy muszą być zgodne z T-001/T-002 i F-006. Bez fikcyjnej gwarancji 100% poprawności, całkowitego braku odpowiedzialności czy trwałej bezpłatności przyszłego produktu.

Zakończenie bety nie jest zgodą na skasowanie lub sprzedaż postępu: właściciel przygotowuje informowanie i zgodny los danych przed faktyczną decyzją o zamknięciu. Nie dodajemy teraz samoobsługowego eksportu; obowiązujące prawa mają ręczną bezpieczną obsługę T-001.

Sprawdzić licencje faktycznie dystrybuowanych zależności/FSRS, materiałów językowych i źródeł. [Wikimedia Terms of Use](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use) wymagają właściwego przypisania/licencji przy ponownym użyciu tekstu; fakt słownikowy i przejęte opracowanie nie są tym samym. Ustalić pochodzenie URL/wersja/licencja/modyfikacja dla rzeczywiście kopiowanych treści, sposób atrybucji w aplikacji i WWW oraz obowiązki dla pochodnych. Nie deklarować, że cały słownik to własny tekst AI, ani że CC BY-SA automatycznie obejmuje cały kod aplikacji. Nie dokładać materiałów bez ustalonego prawa do dystrybucji.

Warunki importu wymagają prawa do przesyłanego materiału, nie przeniesienia wszystkich praw użytkownika na operatora. Ochrona danych, AI i prawa konsumenta wymagają adekwatnego przeglądu Hiszpania/UE; mała grupa znajomych nie zastępuje tego przeglądu. Operator zatwierdza dane identyfikacyjne w kontrolowanym procesie, nie przez wpisanie prywatnych szczegółów do taska.

## Języki i WWW

Publiczne `/privacy`, `/terms`, `/legal`, `/support`, `/delete-account` mają PL/EN/ES i identyfikowalną wersję. Stabilne adresy aktualne zachowane dla Play/maili; niezmienne adresy wersji dla dowodu akceptacji. Android z innym locale jawnie pokazuje dostępne języki dokumentu; fallback nie zmienia języka nauki ani nie udaje tłumaczenia.

F-002 dobiera faktycznych odbiorców/rynki i wymogi lokalne do zrozumiałych informacji; sam komplet PL/EN/ES nie dowodzi zgodności w każdym kraju i dla każdego języka UI. Mail/strony operacji konta nadal mają odrębny katalog 17 locale F-004; nie redukujemy go do trzech.

Wymogi cookies/SDK według T-001: brak trackingu nie jest automatycznym dowodem braku obowiązków. Google uruchamiane po świadomym wyborze, nie wczytywane jako tracker na każdej stronie prawnej; potrzebne technologie transakcyjne opisane adekwatnie.

## Zależności i kryteria

**Start:** decyzje biznesowe/odbiorcy i inwentaryzacja z [E-001/F-007/T-001](./T-001-prywatnosc-i-deklaracje.md). Projekt dokumentów może powstawać wcześniej niż gotowy kod; finalne zatwierdzenie musi porównać tekst z faktycznym zachowaniem.

- [ ] Lista wymaganych informacji i zakres warunków zatwierdzone w przeglądzie odpowiednim dla Hiszpanii/UE; wskazany właściciel akceptacji prawnej.
- [ ] Każda deklaracja odpowiada konkretnemu zachowaniu/specyfikacji; otwarte wymagania mają taski, nie są maskowane disclaimerem „beta”.
- [ ] Publiczne wersje, języki, daty i adresy ustalone; linki i dostęp z auth/ustawień działają na finalnym wydaniu.
- [ ] Sposób akceptacji/informowania, wersjonowanie oraz obsługa starych kont opisane i mają testy.
- [ ] Polityka, Data safety, usuwanie i warunki nie są wzajemnie sprzeczne; płatności pozostają poza E-001.
- [ ] Rejestracja obu metod i dotychczasowe konto: brak/zmiana wersji, odmowa, podwójny tap, niepewny wynik i offline nie tworzą fałszywego dowodu ani nie usuwają pracy.
- [ ] Akceptacja nie zmienia weryfikacji adresu, metod logowania ani lifecycle; pomoc/usunięcie działają również przy braku akceptacji nowych warunków.
- [ ] Pochodzenie/licencje i rzeczywista atrybucja materiałów ustalone; same dependency notices nie zastępują praw do treści słownikowych.

## Źródła sprawdzone 17.11.2026

- [BOE: LSSI, art. 10 — informacje o usługodawcy](https://www.boe.es/buscar/act.php?id=BOE-A-2002-13758#a10).
- [AEPD: obowiązek informowania w aplikacjach mobilnych](https://www.aepd.es/sites/default/files/2019-11/nota-tecnica-apps-moviles.pdf) — art. 13/14 RGPD, niezbędne i opcjonalne przetwarzanie oraz rozdzielenie zgód.
- [AEPD: cookies i technologie podobne](https://www.aepd.es/guias/guia-cookies.pdf) — właściwe wyjątki i zgody wymagają analizy realnego użycia.
- [Google Play: User Data](https://support.google.com/googleplay/android-developer/answer/10144311?hl=en) — prywatność, przejrzystość i usuwanie kont.

To specyfikacja pracy i źródła, nie porada prawna ani zatwierdzony tekst. **Wynik weryfikacji:** brak gotowych dokumentów/akceptacji prawnej; bez implementacji.
