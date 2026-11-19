# T-002 · Internal → zamknięta beta

**ID:** `E-001/F-001/T-002` · **Status:** `in_progress` · **Priorytet / rozmiar:** P0 / M.  
**Feature:** [Prowadzenie bety](../README.md). **Źródło:** B-14, [bramki analizy](../../../sources/analiza-2026-11-17.md#11-bramki-wejścia-i-wyjścia-z-bety).

## Cel i zakres

Przeprowadzić mały internal, potem closed z linkiem opt-in, instrukcją instalacji/migracji, pomocą i obserwacją. Rozszerzenie dopiero po miarach epica, nie po samym uploadzie.

**Warunki uruchomienia:** wymagane P0 z [wydania](../../F-002-wydanie-play/README.md), [sesji](../../F-003-sesja-i-offline/README.md), [e-maila](../../F-004-email-i-hasla/README.md), [Google](../../F-005-google/README.md), [konta](../../F-006-zarzadzanie-kontem/README.md), [prywatności/wsparcia](../../F-007-prywatnosc-i-wsparcie/README.md), [decyzje E-001/F-001/T-001](./T-001-decyzje-i-zakres.md) i końcowa bramka [E-001/F-008/T-001](../../F-008-jakosc-i-operacje/tasks/T-001-bramki-jakosci.md). Wymagane kontrole B-12 nie znikają pod etykietą P1.

## Plan bez kolejnej rundy decyzji

Zatwierdzone: 5–30 dorosłych, self-service bez opłat/zaproszeń do konta, **internal → closed**, docelowo świat, na start zatwierdzone kraje faktycznych testerów. Konta i postęp kontynuowane po becie. Brak terminu kalendarzowego jest celowy: start po dowodach, nie po dacie.

### Gate A — internal, mała grupa kontrolna 2–5

1. Operator potwierdza nazwę/nowy applicationId/domenę/kontakty i właściwy typ/status Play według F-002. Kwoty WARN/HARD AI, rzeczywiste umowy/region/koszt oraz kanał alarmów wpisane przed ruchem. Brak pola nie oznacza domyślnej zgody.
2. Przechodzą CI z realnym izolowanym PostgreSQL, unit/lint/release, podstawowy smoke fizycznego S24 i release z normalnego internal track. Google/App Links, HTTPS i właściwy podpis potwierdzone.
3. Przed prawdziwymi kontami działają lifecycle/retencja, przyjęcie zgłoszenia i prawa WWW, wyłączenie raw logów, pierwsza niezależna kopia/dziennik oraz powiadomienie operatora. Internal nie jest pozwoleniem na wysyłanie danych do niesprawdzonego AI/mail.
4. Instrukcja i znane ograniczenia wysłane prywatnie, test przejścia stary debug zgodnie z F-002/T-001. Nie wyłączać auth starych wydań przed przygotowaniem migracji/ocaleniem pracy.
5. Jeśli krytyczny test FAIL/BLOCKED, najpierw poprawka i powtórzenie; nie rozszerzać grupy, bo Play przyjął AAB.

### Gate B — closed, 5–30 osób

Wszystkie A-01…A-24 z aktualnymi dowodami, obowiązkowe P0/B-12, pełna próba RPO ≤1 h/RTO ≤24 h po wykryciu, zgodny listing/Data safety/delete URL/recenzent i realnie zatwierdzone kraje. Przejście tracków z opt-out internal zgodnie z F-002/T-002. Pięciu nowych testerów wykonuje bez podpowiedzi instalację→konto→profil→pierwszą powtórkę; obserwator zapisuje wynik/czas/błąd bez nagrywania haseł i prywatnej biblioteki.

Jeśli konto personal wymaga 12/14, rekrutacja w closed musi potem osiągnąć co najmniej 12 opt-in przez 14 kolejnych dni przed wnioskiem do production. Nie blokuje to startu mniejszej closed ani nie zmienia minimum pięciu osób dla miary produktu.

### Gate C — rozszerzenie i koniec E-001

Po **7 pełnych dniach obserwacji** bez nierozwiązanego krytycznego crash/ANR/mieszania kont/utraty danych, po osiągnięciu progów login/offline/support i obsłużeniu feedbacku operator decyduje o rozszerzeniu closed. Ograniczony Vitals przy małej próbie uzupełniają zgłoszenia i ręczne próby, nie „0 danych = 0 awarii”.

Każdy kolejny kraj przechodzi F-002/T-002, a kolejny build próbę aktualizacji z outboxem. Nierozwiązane niekrytyczne P1 mają właściciela, termin i jawny wpływ; brak odstępstwa dla bezpieczeństwa danych/auth/usuwania. Zamknięcie epica = uzyskane miary + decyzja właściciela + zapis ograniczeń, **nie publiczna premiera**.

## Obsługa i zatrzymanie

Jedna kolejka uwag z wersją aplikacji, scenariuszem, oczekiwanym/realnym wynikiem i stanem triage; content report/outbox oraz e-mail F-007 pozostają wejściami. Nie wymuszać konta GitHub ani instalacji debug builda. Pierwsza odpowiedź człowieka celowo do 2 dni roboczych.

P0 zatrzymuje dystrybucję/rozszerzenie natychmiast po rozpoznaniu przez operatora; ocenić potrzebę ograniczenia dotkniętych API, powiadomić grupę, wykonać runbook F-008/T-004. Nie kasować Room ani resetować bazy, żeby uciszyć błąd. Poprawka Android ma wyższy code, backend kompatybilny schemat; wznowienie po powtórce scenariusza i świadomej decyzji.

Wynik każdego gate: data, wersje/commit/hash, PASS/FAIL/BLOCKED, dowody z F-008, odstępstwa i decyzja operatora. Lista osobowych kontaktów/testerów, login recenzenta i sekrety poza Git; w repo tylko zanonimizowane podsumowanie.

## Kryteria i weryfikacja

- [ ] Przed internal spełniono jego bramkę; zapisano ograniczenia i wyniki z właściwego AAB.
- [ ] Przed closed spełniono osobną bramkę P0, A-01…A-24 mają wyniki, odstępstwa mają właściciela.
- [ ] Co najmniej 5 nowych testerów przechodzi główną ścieżkę bez pomocy; działa przyjmowanie i obsługa zgłoszeń.
- [ ] Jest decyzja o rozszerzeniu po okresie obserwacji i procedura zatrzymania rolloutu/poprawki z wyższym versionCode.
- [ ] Jeśli właściwe konto Play podlega 12 testerom/14 dni, zweryfikowano ten osobny warunek dostępu do produkcji.

**Poza zakresem:** gwarancja produkcyjnej akceptacji Play, publikacja bez osobnego zlecenia.  
**Wynik weryfikacji:** przygotowana procedura i miary; nie uruchomiono tracków, nie zaproszono testerów i nie uzyskano wyników produktu.
