# Operacje bety: alerty, limit AI, odtworzenie bazy

Krótka instrukcja dla operatora. Nie zawiera sekretów ani adresów; wartości ustawia się w Railway.

## Zmienne środowiska (Railway)

| Zmienna | Znaczenie |
|---|---|
| `AI_MONTHLY_WARN_USD`, `AI_MONTHLY_HARD_USD` | Miesięczny próg ostrzeżenia i twardy limit wydatków AI (UTC). Wymagane `0 < WARN ≤ HARD`. |
| `OPERATOR_NAME`, `SUPPORT_EMAIL` | Dane operatora i monitorowany adres wsparcia (też w dokumentach prawnych). |
| `OPERATOR_ALERT_EMAIL` | Adres alertów; bez niego alerty idą na `SUPPORT_EMAIL`. |
| `ANDROID_PACKAGE`, `MIN_APP_VERSION_CODE`, `APP_UPDATE_URL` | Pakiet release i wymuszenie aktualizacji (HTTP 426); `0` = bramka wyłączona. Procedura: [wydanie Androida](./wydanie-android.md#wymuszenie-aktualizacji-http-426). |

Bez tych zmiennych `/health/ready` zwraca 503 (w logu tylko nazwy pól). Monitor zewnętrzny (UptimeRobot Free) powinien odpytywać `/health/ready` co 5 minut.

## Alerty (co 15 minut, deduplikowane, przypomnienie najwyżej co 6 h)

- `ai_budget`: poziom 1 = 70% WARN, 2 = 90% WARN, 3 = powyżej WARN, 4 = osiągnięty HARD (nowe płatne wywołania stoją, karty czekają jako `waiting_budget`).
- `ai_unresolved`: wywołania z nieznanym kosztem liczone zachowawczo. Uzgodnij z fakturą dostawcy i wywołaj `ai_budget.resolve_unresolved(okres, koszt)`.
- `mail_stuck`: najstarszy mail kolejki czeka ponad 10 minut.
- `purge_stuck`: usuwanie konta bez postępu ponad godzinę lub termin w ciągu 24 h.
- `reports_overdue`: zgłoszenie treści bez odpowiedzi ponad 36 h.
- Brak świeżego heartbeat (ponad 30 min) = `/health/ready` 503.

Alerty niosą liczby i kwoty, nigdy adresów, tokenów ani treści.

## Limit AI osiągnięty

1. Karty i wyszukiwania dostają 503 `ai_budget_exhausted` (aplikacja pokazuje komunikat o wstrzymaniu); zapisane dane są bezpieczne.
2. Zdecyduj: podnieś `AI_MONTHLY_HARD_USD` albo poczekaj do 1. dnia miesiąca UTC.
3. Gdy jest miejsce w limicie, cykl utrzymania sam wznawia zaparkowane karty.

## Zatrzymanie rolloutu

Poprawka zgodna ze starym klientem: wycofaj wdrożenie w Railway do poprzedniego. Nie usuwaj kolumn ani tabel; migracje są wyłącznie addytywne.

## Odtworzenie bazy z kopii (PITR / backup)

1. Przywróć bazę na osobne środowisko i sprawdź ją; dopiero potem przełącz ruch.
2. Zbierz z logów Railway linie zaczynające się od `account_journal ` z okresu od punktu przywracania (zapisane po commicie, bez adresów i tokenów) do pliku.
3. Najpierw próba (nic nie zapisuje):
   `python -m app.services.restore_recovery --log linie.txt`
4. Zapis: dodaj `--apply`. Gdy linii brak: `--no-journal --apply` (wszystkie konta z hasłem muszą potwierdzić się resetem hasła lub Google).
5. Skutki: wszystkie sesje i dowody unieważnione, nowa epoka synchronizacji (urządzenia pobierają dane od nowa), utracone prośby o usunięcie i usunięcia wznowione, konta ze zmienionymi po punkcie przywracania danymi logowania dostają flagę (logowanie hasłem zwraca 403 `restore_recovery_required` do resetu hasła lub logowania Google). Raport to same liczby.
6. Ręcznie sprawdź przypadki `cancel_needs_manual_review` w raporcie.

Dziennik trzyma zdarzenia 45 dni (poza trwającymi usunięciami). Linie logu Railway muszą być przechowane co najmniej tak długo, jak okno odtwarzania.

## Incydent

Zapisz czas, objaw, alert, decyzję i skutek w prywatnych notatkach (`.local/`), nie w repozytorium. Nie ustawiaj `LLM_STORE_PAYLOADS=true` na Railway.
