# T-001 · Moje konto

**ID:** `E-001/F-006/T-001` · **Status:** `in_progress` · **Priorytet / rozmiar:** P0 / M.  
**Feature:** [Zarządzanie kontem](../README.md). **Źródło:** B-07; F-02/F-15 w [analizie](../../../sources/analiza-2026-11-17.md).

## Cel i zakres

Dodać sekcję konta z e-mailem, weryfikacją, metodami logowania, zmianą hasła lub informacją Google-only, pomocą/prywatnością, usuwaniem i logout. Wyraźnie oddzielić to od profili nauki. Bez obowiązkowego imienia, zdjęcia czy telefonu.

**Decyzja z 21.11.2026:** nie ma zmiany ani korekty adresu; inny adres wymaga nowego konta. Poniższe wcześniejsze odniesienia do tej funkcji są historyczne.

**Uproszczenie UI z 21.11.2026:** konto znajduje się w grupie ogólnej, a nagłówek zawiera adres. Nie wyświetlamy osobnego opisu własności profili ani listy metod logowania; dostępne akcje nadal zależą od metod konta. Wcześniejsze wymagania dotyczące tych opisów poniżej są historyczne.

**Aktualizacja ustawień z 21.11.2026:** niepotwierdzony adres pokazuje akcję „Potwierdź e-mail” zamiast czerwonego statusu. Otwiera ona istniejący proces sprawdzenia i ponownej wysyłki, z obsługą błędów i ograniczenia czasu; po potwierdzeniu stan konta jest odświeżany. Wymóg weryfikacji nauki nadal zależy od konfiguracji backendu. Układ ustawień i pola czasu zmieniono bez zmiany palety. Wygląd, otwarcie dialogu oraz walidację godziny sprawdzono na emulatorze; rzeczywista wysyłka i odbiór na fizycznym telefonie pozostają do sprawdzenia.

**Start integracji:** [E-001/F-003/T-002](../../F-003-sesja-i-offline/tasks/T-002-sesja-androida.md), [E-001/F-004/T-002](../../F-004-email-i-hasla/tasks/T-002-poczta-i-odzyskiwanie.md), [E-001/F-005/T-001](../../F-005-google/tasks/T-001-google-i-laczenie.md). **Akcja usunięcia:** po [E-001/F-006/T-002](./T-002-usuwanie-konta.md); linki pomocy/prywatności zgodne z E-001/F-007.

**Metody logowania:** Google-only widzi osobne „Dodaj hasło” zgodnie z [E-001/F-004/T-005](../../F-004-email-i-hasla/tasks/T-005-dodanie-hasla.md), a nie formularz zmiany nieistniejącego hasła. Pokazać różnicę między adresem aplikacji i podłączonym Google, gdy są różne. W becie brak akcji odłączenia metod. Reguły i macierz stanów są w [F-004](../../F-004-email-i-hasla/README.md#zatwierdzona-polityka-konta--17112026).

## Stan kodu i wejście

[SettingsScreen](../../../../../../android/app/src/main/java/com/vocabulario/app/ui/settings/SettingsScreen.kt) zawiera preferencje nauki/wyglądu i logout, lecz nie kompletną tożsamość konta. [SettingsViewModel](../../../../../../android/app/src/main/java/com/vocabulario/app/ui/settings/SettingsViewModel.kt) zarządza ustawieniami i profilami. Nie dopisujemy do niego całego protokołu bezpieczeństwa: osobny stan/route „Moje konto” otwierany z czytelnej grupy w ustawieniach; istniejące profile i preferencje pozostają na swoich miejscach.

[GET /me](../../../../../../backend/app/api/v1/auth.py) zwraca `id`, `email`, `role`, a od F-004/T-002 (kroki 2b i 5) także `email_verified`, `login_methods` i `email_verification_required`. Android ma już podstawową sekcję „Konto” w Ustawieniach (adres, stan potwierdzenia, Google, zmiana hasła dla kont z hasłem; bez cache, offline pokazuje niedostępność). Pozostałe pola/ekrany poniżej są projektem, nie obietnicą istniejącej funkcji.

## 1. Kontrakt tożsamości

Rozszerzyć istniejący `UserResponse` addytywnie. Autoryzacja sesji według F-003; nie tworzymy nowego endpointu tylko do tego ekranu.

| Pole | Znaczenie |
|---|---|
| `id`, `email`, `role` | Zachowane dotychczasowe pola; ID właściciela nie zależy od adresu. Rola nie jest uprawnieniem nadawanym przez UI |
| `email_verified: boolean`, `email_revision: integer >= 1` | Stan dokładnie bieżącego adresu; cache nie przenosi weryfikacji na inny adres |
| `login_methods: array` | Faktyczne metody z zamkniętego zbioru `password`, `google`; bez duplikatów, co najmniej jedna |
| `google_email: string|null`, `google_email_observed_at: UTC|null` | Ostatni wiarygodny snapshot powiązanego Google z F-005. Nie jest adresem aplikacji ani gwarancją aktualności u dostawcy |
| `account_status: active/deletion_pending/deleting` | Stan cyklu życia z T-002. Normalne `/me` nie omija blokady/revocation dla konta usuwanego |
| `lifecycle_revision: integer >= 1` | Rewizja cyklu życia, nie liczba profili ani wersja lokalnego cache |
| `legal_status` | Addytywny stan zaakceptowanej/wymaganej wersji warunków i potwierdzenia pełnoletności z [F-007/T-003](../../F-007-prywatnosc-i-wsparcie/tasks/T-003-warunki-i-informacje-prawne.md); nie jest weryfikacją e-maila ani nowym dowodem tożsamości |

Brak `google_id/sub`, hashy, refresh/access, dowodów recent-auth, pełnych danych sesji i ustawień innych użytkowników. Brak snapshotu Google przy istniejącym powiązaniu daje „Google podłączone”, nie pozorny brak metody.

Cache odpowiedzi jest właścicielski, z czasem pobrania; zapis/publikacja pod kontrolą owner+generation z F-003. Nie przechowujemy go w globalnych preferencjach, które przejdą na B po logout A. Wadliwy/brakujący `login_methods` nie oznacza Google-only; błąd protokołu i brak mutacji aż do odzyskania poprawnego stanu.

Odczyt przy wejściu i po zakończeniu operacji konta, bez odpytywania w pętli. Równoległe wejścia współdzielą odczyt. Timeout/5xx z cache → ostatnie dane z oznaczeniem i ponowieniem; bez cache → jawny błąd/pusty stan ładowania, nie domyślne inne konto. Po 10 s dostępna akcja ponowienia/wyjścia, nie bezterminowy spinner.

## 2. Zawartość i akcje

1. **Konto aplikacji:** adres, „Potwierdzony”/„Wymaga potwierdzenia”, krótkie wyjaśnienie że profile językowe należą do jednego konta.
2. **Metody logowania:** hasło ustawione/nieustawione, Google podłączone/niepodłączone; przy różnych adresach jawne etykiety „Adres aplikacji” i „Konto Google”. Nie sugerować, że zmiana adresu aplikacji zmienia Google.
3. **Bezpieczeństwo:** akcje zależne od potwierdzonego stanu w tabeli niżej.
4. **Dane i pomoc:** prywatność, warunki/informacje prawne, pomoc, usunięcie konta i logout. Brak nieaktywnych pozornych linków; finalne publiczne URL z konfiguracji F-007.

| Stan/metoda | Dostępne działanie |
|---|---|
| Hasło istnieje | „Zmień hasło” z obecnym hasłem i „Nie pamiętam hasła” do resetu F-004. Google nie zastępuje obecnego hasła tej operacji |
| Google-only | „Dodaj hasło”, z potwierdzeniem podłączonego Google i warunkiem weryfikacji F-004/T-005; brak formularza zmiany nieistniejącego hasła |
| Bez Google | „Połącz Google” zgodnie z F-005: dowód obecnego konta, świadomy wybór Google, bez łączenia po samym e-mailu |
| Google podłączone | Informacja o powiązaniu; bez odłączenia/zamiany metody w becie |
| Adres niepotwierdzony | Wejście do resend/korekty z F-004 i wyjście/pomoc; blokada nauki pozostaje. Usunięcie konta nie wymaga wcześniejszego potwierdzenia błędnie wpisanego adresu |
| Adres aktywny | „Zmień adres e-mail” i stan istniejącego procesu z F-004/T-004; nie druga implementacja tej operacji |
| Offline | Tożsamość z cache oznaczona jako ostatnio pobrana; bezpieczeństwo/usuwanie wymagają sieci. Lokalny logout działa według F-003 |
| Reauth | Ograniczony ekran odzyskania właściciela; brak edycji bezpieczeństwa na samym cache |

Po zmianie/dodaniu hasła lub Google najpierw przyjęcie odnowionej sesji według F-003, potem odświeżenie `/me`; nie resetować ustawień i outboxu. Po zmianie adresu/resetowaniu hasła nowy login, nie pozorne pozostanie zalogowanym. Połączenie istniejących metod nie jest zgodą na scalenie kont.

## 3. Usuwanie, odstąpienie i logout

Proces ma jednego właściciela w [T-002](./T-002-usuwanie-konta.md). Wejście „Usuń konto” wyjaśnia pełen zakres, **7 dni na wycofanie**, potem do 7 dni na fizyczne usunięcie aktywnych danych. Wyraźnie odróżnić od logout i usunięcia jednego profilu/listy. Nie dodajemy eksportu danych jako warunku usunięcia ani nowej funkcji eksportu w tym tasku.

Po przyjęciu: ograniczony ekran z terminem odstąpienia, stanem i „Cofnij usuwanie”, pomocą oraz lokalnym wyjściem. Biblioteka/nauka/import/sync zablokowane; lokalna praca **ukryta i zachowana przez okres odstąpienia**, nie wyczyszczona na samym 202. Nie oferować „Zaloguj ponownie, żeby wrócić do nauki” bez skutecznego anulowania.

„Cofnij usuwanie” wymaga świeżego dowodu według T-002, nie samego linku statusu lub zapisanej starej sesji. Po cofnięciu wymagany zwykły login; te same ID/progress i kolejki, bez wskrzeszania odwołanych sesji. Po granicy odstąpienia przycisk niedostępny z powodem i rzeczywistym statusem serwera.

Logout podczas oczekiwania nie anuluje usuwania. Jeśli lokalne dane czekają, sync jest zablokowany przez proces; użytkownik może najpierw cofnąć usuwanie albo jawnie odrzucić lokalną pracę i wyjść. Nie obiecujemy odtworzenia odrzuconej/odinstalowanej pracy po późniejszym cofnięciu.

## 4. UX, dostarczenie i akceptacja

Formularze jedno wysłanie na raz, bez utraty wpisów po błędzie; hasła i dowody tylko w pamięci, nie `SavedStateHandle`, logach i analytics. Powrót z Google cancel neutralny. Powrót systemowy działa, a timeout mutacji oznacza wynik nieznany i ustaloną ścieżkę odzyskania, nie domyślną porażkę.

17 locale, TalkBack, duża czcionka bez ucinania adresów/akcji, komunikaty nie wyłącznie kolorem. Ekran usunięcia nie wymaga wpisywania angielskiego słowa DELETE ani pełnego adresu jako bariery dostępności; wymaga świadomego potwierdzenia zakresu i świeżego dowodu.

Kolejność: rozszerzenie `/me` → repozytorium/cache owner → ekran i wejścia do istniejących procesów → integracja T-002. Brakujące API w środowisku testowym jest jawną niedostępnością, nie atrapa udanego kliknięcia. Koszty/dostawcy bez zmian; domena i treści prawne nadal F-007, nie warunek napisania UI.

## Kryteria i weryfikacja

- [ ] Na dwóch kontach/dwóch profilach tester rozpoznaje właściciela i wraca do swojej nauki bez pomocy.
- [ ] Google-only nie widzi pozornej zmiany lokalnego hasła; pozostałe akcje mają rzeczywiste ścieżki.
- [ ] Stan Google-only/hasło/obie metody i różne adresy są jednoznaczne; dodanie hasła odświeża stan tego samego konta, bez odłączania Google i kasowania danych.
- [ ] Wszystkie linki i działania sprawdzone, także po błędzie sieci i zmianie konta.
- [ ] Dane `/me` A nie publikują się po loginie B; offline/błąd bez cache nie zgaduje metod konta.
- [ ] Oczekiwanie na usunięcie nie kasuje lokalnej pracy; cofnięcie, za późne cofnięcie i logout nie udają tego samego procesu.
- [ ] Wszystkie 17 locale, TalkBack/duża czcionka i testy stanów konta; A-13/A-21.

**Integracja:** `/me` dodaje po auth `password_upgrade_required` z F-004/T-001; legacy format prowadzi do resetu, nie zmiany po obciętym haśle. Publiczne wersje/URL określa F-007, realna domena/kontakt są gate konfiguracji; `restore_recovery_required` ma pomoc bez zgadywania skrzynki. Finalny test telefonu jest odbiorem implementacji. **Poza zakresem:** redesign profili, nowe dane osobowe i portal WWW do nauki. **Wynik weryfikacji:** analiza kodu i kompletny projekt/integracja, bez implementacji/runtime.
