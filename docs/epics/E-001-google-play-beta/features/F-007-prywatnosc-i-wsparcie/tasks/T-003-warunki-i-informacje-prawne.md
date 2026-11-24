# T-003 · Warunki bety i informacje prawne

**ID:** `E-001/F-007/T-003` · **Status:** `in_progress` · **Priorytet:** P0 przed pierwszą zewnętrzną betą.

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

- Dorośli, proste oświadczenie pełnoletności bez daty urodzenia/dokumentu; projekty dokumentów/pomocy PL/EN/ES z 23.11.2026 pozostają niezatwierdzone. Hiszpański jest proponowany jako wzorcowy ze względu na działalność operatora w Hiszpanii, bez odbierania praw konsumentów w krajach ich zwykłego pobytu. Kraje Play, dane operatora/kontakt i przegląd prawnika pozostają bramką publikacji.
- Dostępność i czas trwania bety, wymagania konta, zasady dozwolonego użycia/importowania treści i koszty, jeśli występują. Nie zakładać przyszłej bezpłatności wszystkich funkcji ani zatwierdzonej waluty.
- Treści AI mogą być błędne; opisać zgłoszenia i ograniczenia bez niezgodnego z prawem wyłączenia odpowiedzialności lub praw konsumenta.
- Zmiana/zakończenie usługi, konta i dostęp do danych: zgodność z procesem usuwania, retencją i umówionym losem danych po becie. Właściciel informuje o 7-dniowym oknie anulowania i celu usunięcia danych aktywnych do 14 dni, nie jako gwarancji; faktycznego purge konta produkcyjnego nie przetestowano. Kopie ręczne i pseudonimowy rekord usunięcia nie mają ustalonego końcowego terminu. Nie zakładać, że zalecenie zachowania kopii wyłącza ewentualne prawa do odzyskania treści po rozwiązaniu umowy.
- Punkty wejścia w Androidzie: przed rejestracją e-mail/Google, ekran weryfikacji i ustawienia. Osobne potwierdzenie otrzymania informacji o prywatności jest propozycją do decyzji właściciela i przeglądu prawnego, nie zgodą na przetwarzanie. Obecne wymuszanie akceptacji po stronie serwera jest wyłączone, a nowe konto Google może je ominąć.
- Dotychczasowe teksty to szkice, nie poprzednia obowiązująca wersja Regulaminu. Pierwszą umowę utworzy dopiero nowa opublikowana wersja; zachować dokładne, niezmienne teksty i dowody akceptacji dla przyszłych zmian.
- Hosting publicznych stron HTTPS, dostęp bez logowania, stabilne adresy dla Play i aplikacji, zachowanie przy braku sieci.

## Mechanizm wersji i akceptacji — projekt

### Dokumenty i dowód

Poniższy wariant z osobnym potwierdzeniem prywatności jest projektem, nie zaakceptowaną decyzją produktową ani samodzielnym wymogiem RODO.

Jeden manifest publikowanych wersji po stronie backendu/WWW: `terms_version`, `privacy_version`, data publikacji/obowiązywania, język, URL i zachowana kopia niezmiennego tekstu (digest jako dodatkowy dowód integralności, nie zamiast tekstu). Wersja warunków identyfikuje uzgodniony komplet PL/EN/ES, nie trzy różne umowy. Zmiana tekstu aktualizuje wersję; nie podmieniać historii pod tym samym identyfikatorem.

Minimalny dowód przy User.id: zaakceptowana wersja warunków i locale, czas serwera, osobna wersja/znacznik otrzymania informacji prywatności, wersja treści oświadczenia pełnoletności i czasy potwierdzeń. Bez daty urodzenia, skanu, raw IP, fingerprintu, hasła i Google tokena. Historia wersji publicznych nie jest historią osób. Retencja osobowego dowodu wymaga ustalenia przed publikacją.

Warunki, prywatność i informacja o AI są rozróżnione:

- Niezaznaczone oświadczenie „Mam co najmniej 18 lat”, osobna niezaznaczona akceptacja warunków oraz osobne pole potwierdzenia, że użytkownik otrzymał/mógł przeczytać informację o prywatności. Nie używać „zgadzam się na politykę prywatności”; nie przypisywać temu polu zgody RODO.
- Krótka informacja o prywatności widoczna przed rejestracją oraz dostępna pełna wersja; przekazanie informacji nie może zależeć wyłącznie od zaznaczenia pola.
- Informacja o wysyłaniu tekstu do AI oraz danych przekazywanych przy korektach. Nie nazywać komunikatu „zgodą”, jeśli nie ma odrębnej podstawy wymagającej zgody; prawa i obowiązki ustalić na podstawie faktycznych przepływów.

### API i rejestracja

| Operacja | Proponowany kontrakt |
|---|---|
| `GET /api/v1/legal/current?locale=...` | Publiczny manifest: wersje/daty/URL/digest oraz wskazany faktyczny język dokumentu. Bez danych konta; obsługuje ETag. Backend zwraca dostępne PL/EN/ES, nie udaje tłumaczenia na inne locale |
| Rejestracja e-mail / Google tworzące konto | Rozszerzenie żądania o `legal_acceptance: {terms_version, privacy_notice_version, locale, adult_confirmed:true, privacy_notice_acknowledged:true}`; wersje i locale zweryfikowane na serwerze, czasy tylko serwerowe. Zapis dowodów i User w tej samej transakcji |
| `GET /me` | Addytywne `legal_status: {accepted_terms_version, required_terms_version, adult_confirmed, acceptance_required}`; bez prywatnej historii i sekretów |
| `POST /api/v1/me/legal-acceptance` | Bieżąca sesja i jawnie przesłany komplet jak wyżej; 200 z aktualnym legal_status po commit. Ten sam komplet idempotentny, nie przesuwa pierwotnego czasu. Inna nowsza akceptacja wymaga jawnej akcji |

Nieprawidłowa/nieaktualna wersja w submit →409 `legal_version_changed` z aktualnym manifestem, bez utworzenia konta/automatycznej akceptacji nowej treści. Brak któregokolwiek wymagania →422 bez odbijania sekretów. Walidacja przed efektem tworzenia konta; Google nie tworzy częściowego User przed wykryciem braku warunków. Nie zmieniać reguł linkowania istniejącego konta po `sub`.

Akceptacja online; offline można odczytać ostatnią zapisaną wersję/stan, ale nie pokazywać nowego potwierdzenia jako przyjętego przez serwer. Cache manifestu nie oznacza, że wersja nadal obowiązuje przy submit. Podwójny tap, utrata odpowiedzi i retry nie tworzą kolejnego konta lub fałszywej nowej zgody. Warunki dostępne przed otwarciem wyboru Google/rejestracją i w ustawieniach; nie pytać istniejącego zaakceptowanego użytkownika przy każdym loginie.

### Istniejące konta, istotna zmiana i odmowa

Stare konta nie dostają „zaakceptowano” migracją bez dowodu. Po prawidłowym loginie brak wymaganej akceptacji daje ograniczony stan, nie `invalid_credentials`; **403 `terms_acceptance_required`** dotyczy chronionych operacji nauki/sync. Sesja/właściciel i praca lokalna pozostają, bez zerowania outboxu.

Osobny legal gate, a nie przywracanie odwołanej sesji: dozwolone `/me`, manifest/akceptacja, wymagane potwierdzenie adresu, odzyskanie dostępu/logout, pomoc/prawa i usunięcie konta zgodnie z własnym dowodem F-006. Lifecycle usuwania i brak ważnej sesji mają pierwszeństwo. Akceptacja nie weryfikuje e-maila ani nie cofa usuwania. Po bramce wymaganej weryfikacji/warunków normalna praca dopiero przy spełnieniu obu.

Android zapamiętuje stan przy właścicielu; pierwszy brak potwierdzenia/serwerowe wymaganie blokuje naukę do akceptacji, ale nie kasuje cache. Dotychczas zaakceptowana instalacja nie odkrywa istotnej zmiany, będąc offline: nie obiecujemy zdalnej natychmiastowej blokady, nie dodajemy pollingu. Po otrzymaniu aktualnego wymagania legal gate obejmuje też offline; kontrola owner+generation chroni opóźnione odpowiedzi. Niedostępny manifest daje retry/pomoc, nie domyślne zaakceptowanie.

Istotna zmiana: publikacja nowej czytelnej wersji i streszczenia zmian, ustalony termin, ocena prawna potrzeby ponownej akceptacji/innej zgody; backend egzekwuje wymagany zestaw, nie dowolny numer klienta. Pierwsza opublikowana wersja musi być zaakceptowana przez nowe i istniejące konta przed dostępem do chronionych funkcji; brak akceptacji nie usuwa konta ani nie wyraża zgody. Pozostają pomoc/prawa/logout/usunięcie.

## Treść i prawa do materiałów

Dokumenty opisują rzeczywiste konto, metody Google/hasło, prywatne profile/naukę, lokalne przypomnienia, bezpłatną betę, niedoskonałość AI i zgłoszenia. Opisują też status produkcji, a nie tylko kod: Railway w Amsterdamie według właściciela, nieznane wygaśnięcie niektórych kopii, brak potwierdzenia wdrożenia czyszczenia historii/importów/cache na 24.11.2026 oraz osobny zapis „pokaż więcej” bez TTL. Nie twierdzić, że wszystkie kopie znikają w 30 dni ani że 14 dni usuwania to gwarancja.

Zakończenie bety nie jest zgodą na skasowanie lub sprzedaż postępu: właściciel przygotowuje informowanie i zgodny los danych przed faktyczną decyzją o zamknięciu. Prawnik musi ustalić zakres Dyrektywy 2019/770 i ewentualne prawo do odzyskania treści w formacie maszynowo czytelnym; jeśli obowiązuje, zaprojektować i przetestować działający eksport/udostępnienie przed publikacją.

Sprawdzić licencje faktycznie dystrybuowanych zależności/FSRS, materiałów językowych i źródeł. Kod obecnego przepływu wskazuje Wikisłownik jako pomocnicze źródło oceny korekt, nie zwykłych wyszukiwań; bezpośrednie wyświetlanie wpisu użytkownikowi nie zostało potwierdzone. Zweryfikować API/warunki Wikimedia, co dokładnie wysyła się i czy odpowiedź modelu może odtworzyć treści słownikowe. Ustalić wymagania licencji/atrybucji na podstawie konkretnego ponownego użycia; nie twierdzić, że każde użycie obejmuje CC BY-SA ani że treści są wyświetlane bez dowodu.

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

## Źródła sprawdzone 23.11.2026

- [BOE: LSSI](https://www.boe.es/buscar/act.php?id=BOE-A-2002-13758), zwłaszcza art. 28; [Dyrektywa 2011/83/UE](https://eur-lex.europa.eu/eli/dir/2011/83/oj/eng), art. 8 ust. 7; [Dyrektywa 2019/770](https://eur-lex.europa.eu/eli/dir/2019/770/oj), art. 3 i 16.
- [RODO](https://eur-lex.europa.eu/eli/reg/2016/679/oj); [LOPDGDD](https://www.boe.es/buscar/act.php?id=BOE-A-2018-16673); [AEPD: apps móviles](https://www.aepd.es/guias-y-herramientas/guias).
- [Komisja Europejska: AI Act transparency rules](https://digital-strategy.ec.europa.eu/en/factpages/quick-facts-transparency-rules-ai-systems) and [Regulation (EU) 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj).
- Google Play: [User Data](https://support.google.com/googleplay/android-developer/answer/10144311), [account deletion](https://support.google.com/googleplay/android-developer/answer/13327111), [trader status](https://support.google.com/googleplay/android-developer/answer/17594752), [new personal-account testing](https://support.google.com/googleplay/android-developer/answer/14151465).
- Current code and factual owner updates are summarized in the [legal draft index](../../../../../reference/dokumenty-prawne/README.md).

This is a work specification and source list, not legal advice or approved wording. The project documents exist as unpublished drafts; legal approval, code changes for acceptance/receipt, production retention deployment and deletion verification remain outstanding.

**Projekty z 23.11.2026:** [dokumenty prawne ES/PL/EN](../../../../../reference/dokumenty-prawne/README.md) — nota prawna, regulamin i polityka prywatności do przeglądu prawnego, wraz z ustaleniami, brakami i źródłami. Publiczne w repo, lecz niewdrożone jako dokumenty usługi; wersja `2026-06-01` bez zmian. Pierwsza wersja Regulaminu dopiero po zatwierdzeniu i implementacji wersjonowania, potwierdzenia trwałym nośnikiem i wymaganej akceptacji.
