# Bramki bety: internal → closed → rozszerzenie

Lista kontrolna operatora i szablon wyniku. Kontrakt: [E-001/F-001/T-002](../epics/E-001-google-play-beta/features/F-001-prowadzenie-bety/tasks/T-002-uruchomienie-bety.md). Dane testerów, loginy i sekrety trzymaj poza Git; w repozytorium tylko zanonimizowane podsumowanie.

## Gate A: internal (2–5 osób)

- [ ] Nazwa, applicationId, domena i kontakty potwierdzone ([wydanie](./wydanie-android.md)); `OPERATOR_NAME`, `SUPPORT_EMAIL`, limity AI i `OPERATOR_ALERT_EMAIL` ustawione, `/health/ready` = 200 ([operacje](./operacje-beta.md)).
- [ ] CI zielone, release z właściwego AAB, smoke na fizycznym S24, kontrola 16 KB (`scripts\check_aab_16kb.py`), podpis Play App Signing, App Links/HTTPS.
- [ ] Działają: zgłoszenia i prawa WWW, retencja, wyłączone raw logi (`LLM_STORE_PAYLOADS` nie `true`), pierwsza kopia i dziennik konta, alerty do operatora.
- [ ] Instrukcja instalacji i znane ograniczenia wysłane prywatnie; sprawdzono przejście z debug (wyślij kolejki, potem nowa instalacja).
- [ ] Krytyczny FAIL/BLOCKED: najpierw poprawka i powtórka, grupy nie rozszerzamy.

## Gate B: closed (5–30 osób)

- [ ] A-01…A-24 z aktualnymi dowodami, odstępstwa mają właściciela.
- [ ] Próba odtworzenia z kopii: RPO ≤ 1 h, RTO ≤ 24 h.
- [ ] Listing, Data safety, adres usuwania konta i konto dla recenzenta zgodne z aplikacją; zatwierdzone kraje.
- [ ] 5 nowych testerów bez podpowiedzi: instalacja → konto → profil → pierwsza powtórka (wynik, czas, błąd; bez haseł i prywatnej biblioteki).
- [ ] Konto personal z wymogiem 12 testerów / 14 dni: osobna weryfikacja przed wnioskiem o produkcję.

## Gate C: rozszerzenie

- [ ] 7 pełnych dni bez krytycznego crash/ANR, mieszania kont ani utraty danych; progi login/offline/support osiągnięte.
- [ ] Feedback obsłużony; niekrytyczne P1 mają właściciela i termin.
- [ ] Każdy kolejny kraj: [F-002/T-002](../epics/E-001-google-play-beta/features/F-002-wydanie-play/tasks/); kolejny build: próba aktualizacji z niewysłaną kolejką.
- [ ] Decyzja operatora zapisana. To nie jest publiczna premiera.

## Obsługa i zatrzymanie

Jedna kolejka uwag: wersja aplikacji, scenariusz, oczekiwany i faktyczny wynik, stan triage. Pierwsza odpowiedź człowieka do 2 dni roboczych. Nie wymuszaj konta GitHub ani buildu debug.

P0: wstrzymaj dystrybucję i rozszerzanie, oceń ograniczenie dotkniętych API, powiadom grupę, wykonaj [runbook](./operacje-beta.md). Nie kasuj danych lokalnych ani bazy, żeby uciszyć błąd. Poprawka Androida ma wyższy `versionCode`, backend zgodny schematem. Wymuszenie aktualizacji: [HTTP 426](./wydanie-android.md#wymuszenie-aktualizacji-http-426). Wznowienie po powtórce scenariusza i decyzji operatora.

## Szablon wyniku bramki

```text
Bramka:            A | B | C
Data (UTC):
Build:             versionName / versionCode / commit / SHA-256 AAB
Backend:           commit / wersja wdrożenia
Wynik:             PASS | FAIL | BLOCKED
Dowody F-008:      /health/ready, alerty, kopia/odtworzenie (daty, bez adresów)
A-01…A-24:         liczba PASS / FAIL / BLOCKED
Odstępstwa:        opis, właściciel, termin
Decyzja operatora: kontynuować | poprawić | wstrzymać
```
