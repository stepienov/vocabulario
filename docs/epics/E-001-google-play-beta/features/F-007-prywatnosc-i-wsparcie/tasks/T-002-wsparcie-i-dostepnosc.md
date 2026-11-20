# T-002 · Wsparcie, dostępność i przewidywalne przypomnienia

**ID:** `E-001/F-007/T-002` · **Status:** `in_progress` · **Priorytet / rozmiar:** P1 z wymaganymi kontrolami przed betą / M.  
**Feature:** [Prywatność i wsparcie](../README.md). **Źródło:** B-12; F-10/F-12/F-15 w [analizie](../../../sources/analiza-2026-11-17.md).

## Cel i zakres

Zapewnić pomoc i zgłoszenie treści, krótkie sensowne oczekiwanie, dostępność oraz przewidywalne lokalne przypomnienia. Zakres ustalony 17.11.2026: wyłącznie lokalne przypomnienia, bez serwerowego push. Rozróżnić korektę językową i zgłoszenie treści niedozwolonej.

**Zależności:** brak blokady dla rozpoczęcia analizy UI; integracja właściciela powiadomień z [E-001/F-003/T-002](../../F-003-sesja-i-offline/tasks/T-002-sesja-androida.md), deklaracje z [E-001/F-007/T-001](./T-001-prywatnosc-i-deklaracje.md), decyzja o powiadomieniach z E-001/F-001/T-001.

## Treści i odbiorcy — zasady kontraktu

Beta jest kierowana do dorosłych. To nie jest zgoda na generowanie treści niedozwolonych przez Play ani zamiennik prawidłowej klasyfikacji treści. Nie przyjmować też automatycznie, że każde słownikowe objaśnienie wulgaryzmu musi być zablokowane.

Taksonomię i wyniki definiuje niżej tabela polityki treści; implementacja korzysta z istniejących promptów/walidatorów bez dodatkowego wywołania LLM dla każdego zapytania. Nie przywracać wyłączonej korekty jako rzekomego kanału bezpieczeństwa.

Zgłoszenie treści niedozwolonej ma być możliwe wewnątrz aplikacji, z potwierdzeniem i obsługą przez twórcę. Sama korekta lingwistyczna ani etykieta „18+” nie dowodzą spełnienia wymagań. Przygotować konkretne testy wielojęzyczne, w tym fałszywe blokady zwykłego użycia słownikowego i nieskuteczne blokady generacji.

[Google Play: AI-Generated Content](https://support.google.com/googleplay/android-developer/answer/13985936?hl=en), sprawdzone 17.11.2026. Faktyczny zakres zastosowania i zabezpieczeń trzeba potwierdzić dla finalnej aplikacji.

## Zatwierdzony kanał i oczekiwanie

Właściciel zatwierdził **cel pierwszej odpowiedzi człowieka do 2 dni roboczych**. Nie jest to termin naprawy, gwarancja pracy 24/7 ani ustawowy termin realizacji praw. Monitorowany e-mail służy problemom konta/betą i prawom użytkownika; zgłoszenie niewłaściwej treści działa bez wychodzenia z aplikacji. Bez nowego SaaS helpdesk. Konkretny publiczny adres i jego dostawca zostaną ustalone przy domenie, bez pozyskiwania prywatnego adresu w tym dokumencie.

Robocze reguły obsługi: dni robocze poniedziałek–piątek poza świętami właściwymi dla operatora; przed publikacją wskazać kalendarz/strefę na stronie pomocy. Pilne bezpieczeństwo/prywatność trafia do priorytetowej oceny niezwłocznie po zauważeniu; cel supportu nie odracza właściwej obsługi incydentu F-008. Nie obiecywać automatycznego wykrycia przez całą dobę.

Pomoc jest dostępna z auth/weryfikacji/reauth, „Moje konto” i stanu usuwania. Pokazuje adres do skopiowania, nie tylko intent do aplikacji pocztowej; brak klienta mailowego daje drogę do WWW/kopiowania. Publiczna pomoc i szablony odpowiedzi PL/EN/ES; kontrolki Androida we wszystkich 17 locale.

## Stan faktyczny

- [CardCorrectionFlow](../../../../../../android/app/src/main/java/com/vocabulario/app/ui/card/CardCorrectionFlow.kt) ma `CARD_CORRECTION_ENABLED = false`: nie traktujemy obecnego UI jako dostępnego raportowania.
- [API korekt](../../../../../../backend/app/api/v1/learning.py) tworzy `CardCorrection`, zmienia stan aktywności/review karty i uruchamia [process_correction](../../../../../../backend/app/services/card_corrections.py). To odrębna ścieżka korekty z limitem i automatyzacją; nowy raport bezpieczeństwa nie może od niej zależeć.
- [Scheduler](../../../../../../android/app/src/main/java/com/vocabulario/app/notifications/NotificationScheduler.kt) używa `setAlarmClock`, ma fallback oraz osobne okresowe zadanie enrichment. [Receiver](../../../../../../android/app/src/main/java/com/vocabulario/app/notifications/StudyReminderReceiver.kt) sięga po repozytorium i używa OR ustawień/prefs; odczyt nie jest dowodem pracy wyłącznie lokalnej ani izolacji kont.
- [Helper](../../../../../../android/app/src/main/java/com/vocabulario/app/notifications/NotificationHelper.kt) kontroluje ogólną zgodę, ale blokada kanału i pełny stan sesji/owner wymagają integracji. Nie zmieniamy przypadkiem ścieżki gotowości kart.

## Raport treści — minimalny proponowany kontrakt

### Zapis i odpowiedzi

Rozszerzyć istniejące FastAPI/PostgreSQL oraz panel administratora, nie tworzyć oddzielnej usługi ani kolejki LLM. Oddzielny `content_reports` jest uzasadniony inną semantyką niż `CardCorrection`: zgłoszenie bezpieczeństwa nie zmienia statusu nauki i nigdy nie czeka na automatyczny werdykt.

- `POST /api/v1/content-reports`, uwierzytelniony aktywny właściciel: `client_report_id: UUIDv4`, `profile_id`, `target_kind: card|lookup|practice`, opcjonalne `target_id`, `field` z allowlisty, `reason: incorrect|offensive|privacy|other`, `excerpt` do 4000 i `note` do 1000 znaków Unicode. Bez załączników, dowolnego URL i automatycznej biblioteki. Większy tekst użytkownik świadomie skraca w podglądzie, nigdy ciche obcięcie na serwerze.
- Dla wskazanego card/profile sprawdzić ownership wspólnymi helperami; cudzy/brakujący obiekt →404 bez ujawniania. Lookup/practice może być ulotne: excerpt jest **twierdzeniem użytkownika**, nie dowodem pochodzenia i nie poleceniem do wykonania. Nie pobierać cudzych obiektów na podstawie target_id ani automatycznie uruchamiać podanej treści.
- Rekord: report UUID, owner/profil, client UUID, hash kanonicznego requestu, rodzaj/cel/fragment/powód/notatka, wersja aplikacji oraz potrzebne języki, `received_at`, `status: received|in_review|resolved`, `resolution_code`, daty/identyfikator operatora. Bez refresh/JWT, e-maila Google, pełnego urządzenia/IP i payloadów innych wywołań. Kontakt z kontem przez obecny owner, bez kopii adresu w każdym raporcie.
- Unikalność `(user_id, client_report_id)`. Zapis i odpowiedź po commit; **201** `{report_id,status,received_at}`. Dokładne retry zwraca **200** z tym samym rekordem, również po utracie odpowiedzi; inna treść pod tym ID →409 `report_request_conflict`.
- Minimalny `content_report_receipts` unique(owner, client_report_id) utrwala fingerprint/report ID/received_at w tym samym commit. Po usunięciu zamkniętego payloadu +30 dni zachowuje tylko potwierdzenie `expired` do końca konta; nie fragment/note/target FK. Retry starej operacji zwraca 200 ten sam ID/status expired, nie tworzy nowego raportu. Nowy raport wymaga jawnego nowego submit/ID. Receipt sprawdzamy po auth/lifecycle **przed** walidacją istnienia starego targetu; usunięta karta nie zamienia dokładnego retry wcześniej przyjętego raportu w 404.
- `GET /api/v1/content-reports/{report_id}`: tylko owner, aktualny status/daty/bezpieczny kod rozwiązania, bez wewnętrznych notatek operatora. 404 dla obcego/nieistniejącego; nie odpytujemy okresowo. Zgłoszenia widoczne na żądanie z potwierdzenia/pomocy.
- Po retencji szczegółów GET receipt pokazuje wyłącznie `expired` i datę przyjęcia, bez deklaracji wyniku merytorycznego. UI odróżnia „przyjęto wcześniej, szczegóły wygasły” od braku zgłoszenia i nie ponawia automatycznie.
- Błędy walidacji 422 bez odbicia treści w logach; sieć/timeout nie pokazują „zgłoszono”, DB failure →503 `report_temporarily_unavailable`. Wspólny ogranicznik F-004, osobny scope raportów: propozycja 10 żądań/min/użytkownika i 30/min/IP, 429 z `Retry-After`, bez limitu dobowego odziedziczonego po korektach.
- Limity są ochroną techniczną, nie powodem wysyłania treści do AI. Lifecycle i kolejność blokad User z F-006 obowiązują przed zapisem. Po blokadzie/usuwaniu pomoc WWW/e-mail nadal działa; zwykła sesja nie omija revocation.

### Interfejs i wynik nieznany

- „Zgłoś treść” przy wyniku lookup, podglądzie/sekcji fiszki i wyniku/przykładzie ćwiczenia. Nie tylko przy już zapisanej karcie: wszystkie generowane powierzchnie mają osiągalny entrypoint. Inwentarz powierzchni stanowi listę odbioru.
- Macierz powierzchni: lookup przed SAVE; znaczenie/definicja; przykład i tłumaczenie; skojarzenie/powiązania; materiał importowanej karty; pytanie/odpowiedź/informacja zwrotna w practice/flashcards/typing. `field` ma zamknięte kody `meaning|definition|example|translation|association|related|question|answer|feedback|other`; lookup/card/practice oznacza źródło, nie ograniczenie raportowania do jednego ekranu.
- Formularz pokazuje powód, fragment, opcjonalną notatkę, jakie dane kontekstu zostaną wysłane, i ostrzeżenie przed sekretami/cudzymi danymi. Przycisk potwierdza wysłanie; nie uruchamia ukrytej diagnostyki.
- Jeden aktywny submit, 15 s timeout/5 s connect zgodnie z F-004. Lokalny szkic i client_report_id zapisane atomowo **przed HTTP** w istniejącej właścicielskiej Room/outbox, nie globalnych prefs. Bez nowej samodzielnej bazy/kolejki. Ten sam owner+generation i jawna kategoria raportu w liczniku oczekującej pracy F-003.
- Offline: „Zapisano na tym urządzeniu, jeszcze nie wysłano”, możliwość anulowania. Po niepewnym wyniku retry tego samego requestu; niezmienny payload po pierwszej próbie, edycja tworzy nowy jawny raport. Nie deklarować potwierdzenia człowieka na samym 201.
- Szkic/notatka nie przechodzą do konta B. Reauth zachowuje pracę; logout oferuje sync/pozostawienie według istniejącego kontraktu/jawne odrzucenie, usuwanie konta respektuje grace i manifest F-006. Dodanie typu do outboxu wymaga jawnego dispatch/ACK, nie cichego usuwania nieznanego op.

### Obsługa przez człowieka

Lista w istniejącym panelu admin: najpierw sprawy bezpieczeństwa/prywatności, potem wiek zgłoszenia; filtrowanie statusu i wskaźnik zbliżania się/przekroczenia 2 dni roboczych. Dostęp wyłącznie operatorom z właściwym uprawnieniem, nie zwykłemu użytkownikowi po podaniu ID; renderować tekst jako tekst, nie HTML/polecenie.

Operator przechodzi received → in_review → resolved z kodem i krótką odpowiedzią. Przekazanie do ręcznej poprawki/ograniczenia źródła jest osobnym, audytowanym działaniem; pojedynczy raport nie modyfikuje automatycznie wspólnego słownika ani cudzej karty. Nie mnożymy powiadomień: potwierdzenie w aplikacji, odpowiedź przez monitorowaną pocztę po sprawdzeniu bieżącego uprawnienia/adresu, bez cytowania wrażliwego fragmentu. Anonimowe/podane z zewnątrz adresy nie dostają danych konta.

Cel odpowiedzi mierzymy od serwerowego received_at; dla zwykłego e-maila od przyjęcia przez skrzynkę. Odpowiedź automatyczna nie zamyka celu. Widoczny status „przyjęto” nie znaczy „sprawdzono”. Retencja raportów/maili według T-001, także kopie w skrzynce i panelu; regularny przegląd spraw bez końca i wcześniejszy purge konta.

## Polityka treści i zabezpieczenia generacji — projekt

| Klasa | Zachowanie |
|---|---|
| Zwykłe i wieloznaczne hasło | Neutralne znaczenie/POS/przykład; nie blokować po samym podciągu znaków lub innym znaczeniu w innym języku |
| Wulgaryzm/obraźliwy zwrot w kontekście słownikowym | Neutralne objaśnienie i etykieta rejestru/ostrzeżenie; bez promowania obelgi wobec osoby/grupy i bez dodawania napastliwych przykładów |
| Temat wrażliwy w edukacji | Tylko niegraficzny, rzeczowy kontekst potrzebny do nauki; nie zamieniać słownika w generator treści niedozwolonych |
| Żądanie lub wynik naruszający zasady Play/dostawcy | Odmowa lub bezpieczne ograniczenie: m.in. eksploatacja dzieci, szkodliwe instrukcje, nienawistna przemoc, niedozwolone treści seksualne/oszustwa i ujawnianie danych prywatnych |
| Zgłoszona nieprawidłowość | Potwierdzony raport i ocena człowieka; bez uzależnienia zgłoszenia od wyniku korekty językowej |

Zabezpieczenia w istniejących promptach i walidatorach wejścia/wyjścia, z obsługą odmowy dostawcy jako jawnego typu wyniku. Nie zapisywać odmowy jako poprawnej karty/glossu, nie oznaczać `ready` ani nie ponawiać innym modelem w celu obejścia odmowy. Błędy transportu/protokołu pozostają błędami, nie odmową treści. Krótka odpowiedź pozwala poprawić zapytanie, wrócić i zgłosić problem.

Nie dodajemy automatycznego dodatkowego LLM do każdego zapytania/raportu. Same instrukcje ani prosta blacklist nie są dowodem skuteczności: wykonawca przygotowuje testy wielojęzyczne i analizę wyników, w tym fałszywe blokady oraz obchodzenie instrukcji przez import/notatki. Nieskuteczne zabezpieczenie wraca do poprawy przed publikacją, a nie do przykrycia etykietą „18+”.

## Przypomnienia lokalne — projekt

- Domyślnie wyłączone. Włączenie przez użytkownika, potem potrzebne `POST_NOTIFICATIONS` na Android 13+; odmowa/brak kanału daje stan „zablokowane w systemie”, drogę do ustawień i normalną naukę. Bez ponawiania pytania przy każdym starcie.
- Zwykła sugestia nauki **nie jest budzikiem**. Propozycja: jedno nieprecyzyjne, jednorazowe lokalne `AlarmManager.setAndAllowWhileIdle` na następną porę; bez `setAlarmClock`, `setExact`, `USE_EXACT_ALARM`/`SCHEDULE_EXACT_ALARM` w finalnym merged manifest i bez proszenia o specjalny dostęp. UI mówi „około wybranej godziny”, bez gwarancji minuty w Doze/ograniczeniach producenta.
- Jeden harmonogram właściciela, nie po jednym na każdy profil. Ustawienie/cache właścicielskie, ze znacznikiem generation; nie OR dwóch potencjalnie starych flag. Receivery i workery ponownie sprawdzają owner/stan przed odczytem i przed publikacją; `ReauthRequired`, usuwanie i logout niczego nie pokazują poprzedniemu kontu.
- Treść ogólna, bez adresu, słów i postępu na ekranie blokady. Nie odczytywać sieci/repozytorium, które może rozpocząć sync/LLM, tylko po to, aby wyświetlić reminder. Lokalny licznik nie jest konieczny; bez danych użyć jawnie ogólnej treści, nie zmyślonego `0`.
- Reboot, zmiana strefy/czasu, aktualizacja aplikacji i ponowne wejście uzgadniają najwyżej jeden następny alarm aktywnego owner. Godzina lokalna; DST: nieistniejąca pora przechodzi do następnej prawidłowej, powtórzona występuje najwyżej raz danego dnia. Unikalny dzienny znacznik owner+data zapobiega duplikatom po odbiorniku/restartach.
- Wyłączenie/logout/bariera konta anuluje alarm i widoczne notyfikacje właściciela. Token/generation w PendingIntent i kontrola publikacji chronią callback sprzed anulowania. Nie używać boot do reaktywacji wylogowanego konta ani nie obiecywać działania po systemowym force-stop.
- Nie dodawać nowego pollingu. Istniejące `EnrichmentCheckWorker` i notyfikacje gotowych kart są osobną ścieżką F-003/E-002: sprawdzić izolację/stany/learnable+examples, nie zastępować ich reminderem ani nie usuwać bez oceny skutków.

[Android: planowanie alarmów](https://developer.android.com/develop/background-work/services/alarms), sprawdzone 17.11.2026. Konkretna metoda nieprecyzyjna i zachowanie na urządzeniu są odbiorem implementacji; rezygnacja ze specjalnego dostępu wynika z braku potrzeby precyzyjnego budzika.

## Dostępność i diagnostyka — projekt

Auth/onboarding, konto, usuwanie/cofnięcie, raport i podstawowa nauka: TalkBack z nazwami/rólami i logicznym fokusem, błędy ogłaszane bez ciągłego resetu fokusu, 200% font, mały ekran, IME/klawiatura, jasny/ciemny motyw oraz RTL. Kontrolki min. 48 dp, tekst/stan nie tylko kolorem; ważne przyciski i zgody nie znikają pod klawiaturą.

Oczekiwanie ma anulowanie/wyjście i jawny wynik nieznany; obrót/background/restart nie powtarza submit ani nie gubi szkicu. Timeout nie zamienia się w nieudane hasło lub zakończony raport.

Opcjonalna diagnostyka do pomocy ma podgląd: wersja/build/API/system, bezpieczny request ID i kod błędu. Bez automatycznego logcat, raw HTTP, tokenów, adresów, całego importu/biblioteki. Dodatkowy fragment użytkownik wpisuje świadomie. Nie dodajemy SDK analityki/crash reporting w ramach tego tasku; rzeczywisty wybór diagnostyki należy do F-008/T-001 z T-001.

## Kryteria i weryfikacja

- [ ] A-17: odmowa zgody nie blokuje nauki; strefa/reboot/logout i konto B nie dziedziczą przypomnień A.
- [ ] Zasadność exact alarm sprawdzona; UI/sklep opisują lokalne przypomnienia i nie obiecują serwerowego push.
- [ ] A-21: TalkBack, 200% font, mały ekran, klawiatura, motywy i RTL pozwalają obsłużyć kluczowe akcje.
- [ ] A-20/A-22: timeout daje drogę wyjścia; zgłoszenie ma potwierdzony zapis bez wymogu negatywnej automatycznej korekty.
- [ ] Diagnostyka dobrowolna i zredagowana, bez tokenów/haseł/pełnej biblioteki lub importu.
- [ ] Raport lookup/karty/ćwiczenia: offline, utrata odpowiedzi po commit i retry dają jeden report; cudzy ID nie ujawnia danych, payload konfliktowy nie nadpisuje.
- [ ] Raport trafił do kolejki operatora bez LLM i bez zmiany learnable/ready; można podjąć sprawę, odpowiedzieć i zmierzyć pierwszą odpowiedź, nie sam auto-ACK.
- [ ] Remindery bez sieci nie wywołują HTTP/LLM; odmowa uprawnień, blokada kanału, DST/reboot i callback owner A po login B nie tworzą złych notyfikacji.
- [ ] Zabezpieczenia treści testują zwykłą leksykę/wieloznaczność/rejestr i niedozwolone generacje w kilku językach, bez dodatkowego wywołania przy każdym poprawnym zapytaniu.

**Podział:** raport/API/panel → trwała wysyłka i UI → zabezpieczenia treści → lokalne alarmy/dostępność; bez nowych numerów równoległego planu. Inwentarz i kontrakt są powyżej, dispatch/ACK/owner w F-003/T-003, operator-właściciel/e-mail i alerty w [F-008/T-004](../../F-008-jakosc-i-operacje/tasks/T-004-monitoring-koszty-i-incydenty.md). Adres/domena nie muszą być kupione dla projektu; muszą działać przed zaproszeniem testerów.

Wymagane kontrole bezpieczeństwa/polityki przed closed; reszta P1 przed rozszerzeniem. **Poza zakresem:** FCM/server push, automatyczny audyt każdej karty przez dodatkowy LLM i przywracanie wyłączonego edytora/korekt. **Wynik weryfikacji:** kod/polityki i cel supportu sprawdzone, projekt opisany; brak implementacji i testów runtime.
