# T-002 · Gotowość konta Play Console do dystrybucji

**ID:** `E-001/F-002/T-002` · **Status:** `ready` · **Priorytet / rozmiar:** P0 przed dystrybucją / M.  
**Feature:** [Wydanie Play](../README.md). **Źródło:** [decyzje startowe](../../F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md).

## Cel i zakres przygotowania

Na osobne zlecenie przeprowadzić właściciela przez poniższą checklistę, uzyskać statusy Console i przygotować dystrybucję **internal → closed**, bez open/production w E-001. `ready` oznacza gotową procedurę z rozgałęzieniami, nie zweryfikowane konto.

Fakty od właściciela 17.11.2026: konto utworzone w **2026**, zapłacona prawdopodobnie opłata deweloperska; reszta nieustalona. Nie wiemy, czy personal/organization, czy zakończono weryfikację i czy cokolwiek wysłano. **Zapłata nie potwierdza żadnego z tych faktów.** Nowy applicationId wybrany jako kierunek; wartość przed pierwszym uploadem. Cel długofalowy: świat, ale beta wyłącznie w krajach rzeczywistych testerów po sprawdzeniu obowiązków.

## 1. Konto, uprawnienia i dane publikowane

- Faktyczny typ konta: osobiste/organizacji, właściwy profil i wymagania dla tego typu. Nie wywodzić typu wyłącznie ze statusu działalności ani nie zmieniać go w ciemno.
- Wymagane deklaracje przedsiębiorcy, weryfikacje tożsamości/organizacji, własności witryny i numerów telefonu. Kolejność na podstawie aktualnych komunikatów Console.
- Organizacja może wymagać D-U-N-S i dokumentów właściwych dla kraju; zakres potwierdzić w Console, nie zbierać ich w zadaniu.
- Weryfikacja witryny organizacji jest innym celem niż publiczna strona aplikacji. Najpierw ocenić istniejącą właściwą witrynę; nie uzależniać weryfikacji od pełnego marketingowego serwisu aplikacji, jeśli Console tego nie wymaga.
- Konto osobiste utworzone po 13.11.2023 może podlegać testowi 12 osób/14 dni przed wnioskiem o production access. Nie narzucać tego automatycznie organizacji i nie traktować jako zakazu wcześniejszego internal/closed.
- Przy nowym personal sprawdzić weryfikację prawdziwego urządzenia w aplikacji Play Console; [wymagania](https://support.google.com/googleplay/android-developer/answer/14316361?hl=en) m.in. Android 10+ bez roota. S24 może służyć po sprawdzeniu warunków, sama nazwa telefonu niczego nie potwierdza.
- Przyjęcie do internal/closed: lista/grupa, opt-in link, konto Google testera i instrukcja instalacji. To nie jest konto aplikacji i nie determinuje jej adresu loginu.

Nie zmieniać personal na organization, kraju profilu płatności ani danych prawnych „żeby przejść szybciej”. Właściciel rozstrzyga prawdziwy trader status według definicji, nie tylko płatności w aplikacji. Bezpłatna beta nie dowodzi non-trader. Sprawdzić aktualną [deklarację trader](https://support.google.com/googleplay/android-developer/answer/17594752) i regionalne ujawnienia.

Właściciel przed zatwierdzeniem widzi, które legal name/kraj/adres/kontakt Google pokaże publicznie dla jego typu konta/regionu. Nie dawać obietnicy, że prywatny adres na pewno pozostanie ukryty. Do Google przekazuje właściciel bezpośrednio, nie asystent przez repo.

Wynik: prywatny dowód statusu w Console, data, typ konta, nazwa bramki i właściciel ewentualnej blokady, bez kopii dokumentów tożsamości. W repo wystarcza „identity verified / device verification pending”; problem konta nie jest błędem AAB.

## 2. Nowa aplikacja i listing

1. Właściciel potwierdza ostateczną nazwę i **nowy applicationId przed pierwszym uploadem** według T-001. Nie zakładać, że identyfikator zmienimy później przy rebrandingu.
2. Ustawić free, bez zakupów/reklam w zakresie bety; deklaracje tylko zgodne z finalnym AAB/SDK. Dorosła grupa docelowa 18+ nie jest automatycznie IARC 18+ i nie zwalnia z oceny treści.
3. Listing PL/EN/ES: ikona/grafika, zrzuty rzeczywistego release bez danych testerów, krótki/pełny opis funkcji, ograniczenia bety i źródło pomocy. Nie obiecywać voice, płatności, pełnego offline generowania czy bezbłędności AI.
4. App content: Data safety zgodna z [F-007/T-001](../../F-007-prywatnosc-i-wsparcie/tasks/T-001-prywatnosc-i-deklaracje.md), privacy URL i delete URL bez loginu aplikacji, wsparcie/warunki, audience/content rating, ads, uprawnienia i deklaracja AI-generated content z mechanizmem zgłaszania F-007/T-002.
5. Wypełnić wszystkie aktualnie wymagane karty Console według faktycznego binarium i przetwarzania. Możliwe zwolnienie internal-only z Data safety nie usuwa zobowiązań privacy i nie jest zwolnieniem closed. Przed closed wymagane kompletne deklaracje.
6. Nie prosić o uprawnienia/storage/mic/exact alarm „na zapas”. Zgodność zależy od scalonego manifestu i SDK, nie tylko deklaracji w źródłowym XML.

### Dostęp recenzenta

`App access`: instrukcja krok po kroku, stały syntetyczny zweryfikowany profil e-mail/hasło i komplet dostępu bez zaproszenia/SMS, z prawidłowo zaakceptowanymi bieżącymi warunkami jak dla zwykłego użytkownika. Nie używać prywatnego Google operatora i nie dodawać endpointu omijającego auth/age/legal.

Recenzent widzi istniejące przykładowe karty i może zgłosić treść/usunąć konto zgodnie z zasadami. Przy operacji niszczącej odtworzyć syntetyczne konto normalnym procesem z nowym User.id przed kolejnym review; nie pomijać okresu grace w kodzie produkcyjnym. Nie opierać demonstracji nauki wyłącznie o chwilowo dostępne AI/budżet. Dane logowania recenzenta wyłącznie w Console/bezpiecznym zasobie, poza Git.

## 3. Kraje: świat jako cel, nie automatyczna zgoda

Przed closed zidentyfikować **kraje zamieszkania rzeczywistych dorosłych testerów**, nie narodowość ani tylko język aplikacji. Nie publikować listy osób/adresów w repo. Domyślnie nie zaznaczać wszystkich krajów. Kraje closed i uprawnienia testerów sprawdzić w Console; internal ma inne reguły dostępności, co **nie** zwalnia z oceny prawnej dla faktycznego odbiorcy.

Każdy dodawany kraj/region otrzymuje wpis kontrolny w prywatnym rejestrze release (bez osób):

| Kontrola | Wymagany wynik / właściciel |
|---|---|
| Rynek i zasady Play | Dostępność usługi/dostawców i zgodność ograniczeń regionalnych, aktualne wymagania Console — operator |
| Administrator/przetwarzający | Dane administratora, rola, umowy/DPA, podprocesorzy, hosting i transfery F-007 — właściciel z właściwym przeglądem |
| Obowiązki lokalne | Prywatność, prawa i kanały, okresy/zgłoszenia, ewentualny przedstawiciel UE/UK lub inne lokalne wymogi — właściwy przegląd prawny |
| Wiek, treść i konsument | Pełnoletni odbiorcy, klasyfikacja/AI/report, przepisy konsumenckie/digital services, trader i publikowane dane — właściciel z przeglądem |
| Język i operacje | PL/EN/ES wystarczają prawnie i praktycznie dla grupy; ewentualna wymagana wersja lokalna, pomoc i godziny — właściciel |
| Decyzja | Data, checked sources, zaakceptowane warunki/ograniczenia, brak nierozwiązanej blokady i zgoda właściciela przed zaznaczeniem w Console |

GDPR nie jest certyfikacją na cały świat. UK wymaga osobnej analizy UK GDPR/transferów/przedstawiciela, a USA to nie jeden uniwersalny zestaw reguł; nie stosować automatycznie wszystkich obowiązków CCPA do pięciu osób, ale sprawdzić progi i inne mające zastosowanie prawa. Dla kolejnego kraju, np. Brazylii, powtórzyć analizę lokalną zamiast uznać podobny alfabet za zgodność.

Jeśli lokalne wymagania nie są spełnione w ramach PL/EN/ES/18+/usług projektu, kraj czeka poza closed do uzupełnienia. Dodanie kraju to gate aktualizacji zakresu/release, bez przymusowego ograniczenia języków nauki. Nie wprowadzamy niewiarygodnej geoblokady opartej tylko na IP jako zamiennika obowiązków.

## 4. Tracki i instrukcja testera

Internal: maksymalnie limit Console (aktualnie do 100), projektowo mała grupa kontrolna 2–5. Lista/grupa i link opt-in w prywatnym kanale, opisać możliwe opóźnienie dostępności linku/buildu do kilku godzin. Instalacja z normalnego tracka sprawdza podpis i aktualizacje; internal app sharing to nie ta sama bramka.

Closed: orientacyjnie **5–30 dorosłych**, realne zatwierdzone kraje, zgoda na udział/instrukcja bety, pomoc, znane ograniczenia. Aby przejść z internal do closed, tester opt-out z internal i opt-in do closed według aktualnej procedury Google; inaczej może dostawać inne wydanie. Lista adresów Google dla dostępu Play nie wyznacza loginu w aplikacji.

Instrukcja: właściwe konto Google w sklepie → opt-in → link instalacji/aktualizacji → utworzenie lub login do właściwego konta aplikacji → weryfikacja/warunki → pierwszy profil/karta/powtórka → pomoc/zgłoszenie → bezpieczne wyjście/usunięcie. Osobna sekcja dla starego debug według T-001; bez porady „wyczyść dane”, gdy istnieje outbox.

Jeśli konto personal z 2026 podlega 12/14, prowadzić zgodny z Console zapis **12 osób opt-in przez 14 kolejnych dni w closed** i rzeczywistej aktywności/feedbacku. Pięciu testerów wystarcza do pierwszej małej grupy, nie tego wymogu. To warunek późniejszego wniosku do production; sam upływ dni nie daje automatycznej akceptacji. Wniosek/publiczny rollout poza E-001.

## 5. Stop, ponowienie i dowód

Przy odrzuceniu: zachować zanonimizowany powód, kategorię konto/listing/binarium, przypisać właściwy task, poprawić i ponowić bez losowej zmiany tożsamości lub rozsyłania APK jako rzekomego Play. Przy problemie użytkownika sprawdzić track/Google konto/versionCode/kraj; nie rozpoczynać od resetu danych aplikacji.

Publiczne legal/support/delete URL muszą działać z komputera i bez sesji na telefonie w PL/EN/ES. Google logowanie/App Links na certyfikacie Play i AAB przyjęty w Console to osobne dowody. Plan publikacji nie jest automatycznym kliknięciem „rollout”.

## Granice bezpieczeństwa

Wyłącznie właściciel składa deklaracje prawne i zatwierdza dane w Google. Dokumenty tożsamości, numery, kody SMS, loginy, płatności i dane testerów pozostają poza repo/czatem. W repo wystarcza zanonimizowany status, rodzaj blokady i właściciel działania. Samo przygotowanie taska nie daje zgody na operowanie Console ani zmianę witryny/DNS.

## Kryteria i zależności

- [ ] Potwierdzono typ konta i właściwe wymagania, bez domysłów.
- [ ] Lista wymaganych weryfikacji jest aktualna, ma właściciela i kolejność; przy wykonaniu potwierdzono ich zakończenie statusem Console.
- [ ] Wyjaśniono, które dane dewelopera Google publikuje, i uzyskano właściwą akceptację przed publikacją.
- [ ] Uzgodniono internal → closed lub alternatywę i instrukcję dla testerów.
- [ ] Nie ma blokady konta uniemożliwiającej planowaną dystrybucję; wynik nie udaje zatwierdzenia samej aplikacji.
- [ ] Każdy kraj closed ma aktualny kontrolny wpis i zgodę; brak zaznaczonego świata na podstawie samego celu globalnego.
- [ ] Listing/deklaracje/recenzent/URL odpowiadają finalnemu AAB; dane recenzenta i testerów nie są w repo.
- [ ] Tester rozumie różnicę konta Play i aplikacji, przejście internal→closed i zachowanie starej pracy; powtórka po opt-out nie tworzy drugiego konta.

Samo budowanie [T-001](./T-001-release-i-aktualizacja.md) może iść niezależnie; końcowa dystrybucja wymaga obu tasków i bramek jakości. Publiczny serwis ma zakres w [E-001/F-007/T-004](../../F-007-prywatnosc-i-wsparcie/tasks/T-004-publiczny-serwis-aplikacji.md).

**Bramki wykonawcze:** właściciel sprawdza faktyczny typ/status Console, podaje finalne ID/nazwę/URL/kontakty i zatwierdza właściwe deklaracje/kraje. Procedura obsługuje obie gałęzie typu konta bez nowej decyzji biznesowej. **Poza zakresem:** publiczna premiera/wniosek production, certyfikacja prawa całego świata i operacje na Console teraz. **Wynik:** brak operacji w Console; tylko przygotowanie.

## Źródła sprawdzone 17.11.2026

- [Weryfikacja tożsamości dewelopera i kolejność przed potwierdzeniem telefonu](https://support.google.com/googleplay/android-developer/answer/10841920?hl=en).
- [Weryfikacja witryny](https://support.google.com/googleplay/android-developer/answer/13205715?hl=en).
- [Internal, closed i open testing](https://support.google.com/googleplay/android-developer/answer/9845334?hl=en).
- [Testy wymagane od nowych kont osobistych](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en).
- [Dane wymagane i publikowane zależnie od typu](https://support.google.com/googleplay/android-developer/answer/13628312?hl=en), [deklaracja trader](https://support.google.com/googleplay/android-developer/answer/17594752).
- [UK: informacje prywatności](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/the-right-to-be-informed/what-privacy-information-should-we-provide), [transfery](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/international-transfers/a-brief-guide-to-international-transfers/), [CCPA i progi zastosowania](https://www.oag.ca.gov/privacy/ccpa). To źródła checklisty, nie rozstrzygnięcie zastosowania dla właściciela.
