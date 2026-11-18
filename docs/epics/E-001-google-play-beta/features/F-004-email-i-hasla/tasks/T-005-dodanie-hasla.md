# T-005 · Dodanie hasła do konta Google-only

**ID:** `E-001/F-004/T-005` · **Status:** `ready` · **Priorytet:** P0 w uzgodnionym zakresie pierwszej bety.  
**Feature i polityka:** [E-mail i hasła](../README.md#zatwierdzona-polityka-konta--17112026). **Źródło:** [decyzje startowe](../../F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md).

## Uzgodniony rezultat

Zalogowana osoba z Google-only może dodać hasło do tego samego konta po ponownym potwierdzeniu właściwej tożsamości Google i wymaganym potwierdzeniu adresu aplikacji. Potem korzysta z obu metod bez zmiany ID i postępu.

**Sesje i zawiadomienie — zatwierdzone:** pozostałe sesje odwołujemy, bieżącą bezpiecznie odnawiamy. Na adres aplikacji wysyłamy zawiadomienie o dodaniu hasła. Google pozostaje podłączone; operacja nie czyści danych offline.

## Przebieg

1. „Moje konto” pokazuje „Dodaj hasło” tylko przy braku hasła, nie fikcyjną zmianę hasła.
2. Ponowne uwierzytelnienie właściwym Google musi być związane z bieżącym kontem i konkretną operacją; token innego użytkownika lub sam istniejący access token nie wystarczają.
3. Adres aplikacji musi mieć wymagany dowód weryfikacji. Gdy różni się od adresu Google, dowód dotyczący Google nie potwierdza innej skrzynki.
4. Użytkownik podaje nowe hasło według wspólnego kontraktu T-001. Trwały zapis nie może być wykonany przez anonimową ścieżkę resetu ani nadpisywać istniejącego hasła.
5. Po sukcesie ekran pokazuje obie metody, Google pozostaje podłączone; błąd lub anulowanie nie zmienia konta i nie czyści danych.

### Wspólny projekt recent-auth

[F-005/T-001](../../F-005-google/tasks/T-001-google-i-laczenie.md#proponowany-kontrakt-techniczny-google-i-recent-auth) definiuje challenge z nonce i dowód `add_password` na 5 minut, wyłącznie z Google `sub` już podłączonego do bieżącego konta. Dowód jest związany z sesją/wersją i rewizjami; finalny zapis zużywa go w tej samej transakcji co sprawdzenie braku hasła, ustawienie Argon2, rewizje, odnowienie/odwołanie sesji i zawiadomienie. Błędne nowe hasło nie zużywa dowodu; jego TTL nie jest przedłużany. Weryfikacja skrzynki musi być zakończona przed finalnym zapisem, a przy wygaśnięciu dowodu trzeba ponowić Google. Finalny endpoint i odzyskanie po utracie odpowiedzi są określone poniżej, nie w anonimowym resecie.

## Proponowany kontrakt wykonawczy

- `POST /api/v1/auth/password/add`, aktywna sesja, JSON `{"new_password":"...","recent_auth_token":"..."}`. Bez `user_id`, `session_id`, e-maila ani dowolnego Google `sub` w body.
- Sukces 200 z `TokenResponse` F-003; nie tworzymy drugiej tabeli haseł ani dodatkowej flagi, źródłem prawdy jest nullable `User.password_hash`. `/me.login_methods` po sukcesie zawiera `password` i `google`.
- Warunki sprawdzane ponownie pod blokadą: istniejący właściciel, aktywna bieżąca sesja/wersja, brak hasła, podłączone Google i zgodny świeży dowód `add_password`, niezmienione rewizje, potwierdzony bieżący adres. Jeśli potrzebny jest link pocztowy, jego weryfikację wykonujemy przed krótkim recent-auth. Pasujący wiarygodny Gmail/Workspace może potwierdzić adres przy recent-auth Google bez dodatkowego maila zgodnie z F-005.
- Argon2 i walidacja nowych haseł wyłącznie ze wspólnego T-001. Kosztowny hash poza blokadami; tuż przed zapisem ponowna walidacja stanu. Wspólna kolejność z F-003, obejmująca recent-proof, ewentualną oczekującą zmianę adresu i dowody przed outboxem.
- Jeden commit: zużycie dowodu, ustawienie hasha, `credentials_revision += 1`, unieważnienie starych dowodów poświadczeń/oczekującej zmiany adresu, odwołanie innych sesji/retry, zwiększenie wersji bieżącej i wymiana refresh oraz zaszyfrowane zawiadomienie T-002. Google i adres bez zmian.
- 409 `password_already_set`: obecne hasło nie jest nadpisywane, UI przechodzi do rzeczywistej zmiany/resetu. 403 `email_verification_required`; 403 `recent_auth_required`, 409 `recent_auth_used`, 401 sesji, 422 walidacji oraz 429 według wspólnych kontraktów. Żaden błąd nie zwraca nowego hasła ani tokena Google.
- Nie dodajemy osobnej pamięci retry zawierającej hasło. Po utracie odpowiedzi sukces mógł nastąpić: ponowny login podłączonym Google i `/me` pokazują, czy hasło dodano. Nie ponawiamy w ciemno z nadzieją nadpisania; ustawione hasło można zmienić/resetować istniejącymi procesami.
- UI: informacja o nowej metodzie i odwołaniu innych urządzeń → weryfikacja adresu, jeśli potrzebna → nowe hasło i lokalne potwierdzenie → wybór podłączonego Google → finalny POST → obie metody i potwierdzenie. Złe Google/anulowanie wraca do tej samej operacji bez zmiany konta.
- Hasło/dowód pozostają wyłącznie w pamięci formularza; restart wymaga ponownego wpisania i potwierdzenia Google, ale nie kasowania profili/outboxu. Zapis nowej pary tokenów atomowy według sesji Androida. Teksty obejmują 17 locale, menedżer haseł i dostępność.
- Testy: poprawny przypadek z drugą sesją i wiadomością, dwie równoczesne próby (jedno ustawienie/odnowienie/mail), reset/zmiana adresu między hashowaniem a zapisem, walidacja bez zużycia dowodu, rollback bez częściowego hasła/sesji, utrata odpowiedzi po commit i restart z niewysłaną pracą.

## Zależności i granice

- [E-001/F-004/T-001](./T-001-haszowanie-hasel.md): hashowanie/walidacja.
- [E-001/F-004/T-002](./T-002-poczta-i-odzyskiwanie.md): wspólna weryfikacja adresu i mechanizmy tokenów/poczty.
- [E-001/F-005/T-001](../../F-005-google/tasks/T-001-google-i-laczenie.md): weryfikacja Google/recent-auth, bez implementowania drugiego walidatora.
- [E-001/F-003/T-001](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md): kontrakt sesji i dowodu ponownego uwierzytelnienia.
- [E-001/F-006/T-001](../../F-006-zarzadzanie-kontem/tasks/T-001-moje-konto.md): integracja ekranu i metod, bez duplikowania logiki.

Kontrakty wspólne trzeba uzgodnić przed kodowaniem; integracja końcowa nie wymusza czekania projektu UI na gotowe API. Poza zakresem: nowe konto, scalenie bibliotek, odłączenie Google i zmiana istniejącego hasła.

## Kryteria i testy do rozpisania

- [ ] S-01/S-02/S-03/S-09/S-11 z feature'a: poprawne dodanie, błędna tożsamość, ponowienie, konflikt równoległy, Google-only bez obejścia przez reset.
- [ ] Obie metody prowadzą do tego samego ID i zachowują postęp/outbox; hasła i dowody auth nie trafiają do logów.
- [ ] Przy dwóch sesjach bieżąca dostaje odnowione tokeny, pozostała nie autoryzuje nowych żądań ani refresh. Wysłanie zawiadomienia ma test dostarczenia i ponowienia.
- [ ] Niezweryfikowany adres aplikacji inny niż Google nie dostaje automatycznego potwierdzenia.
- [ ] Istniejące hasło nie jest nadpisywane przez operację „dodaj”; odpowiedź po utracie sieci daje bezpieczną drogę odtworzenia stanu.
- [ ] API/PostgreSQL, stany klienta, 17 locale i rzeczywista integracja Credential Manager mają określone przypadki oraz dowody.

**Integracja:** T-001/T-002/T-003/F-005 współdzielą hasher/mail/proof, F-003 zapis sesji i [commit/journal](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md#6-atomowość-i-wspólny-kontrakt-operacji-konta), F-002/T-001 wydanie. Pierwsze hasło również rejestruje security intent/revisions F-008/T-003 przed commit; nie omija ograniczenia bcrypt/reset ani istniejącego hasła. Brak dodatkowej otwartej decyzji biznesowej.

**Wynik weryfikacji:** brak implementacji i testów runtime; przygotowanie specyfikacji.
