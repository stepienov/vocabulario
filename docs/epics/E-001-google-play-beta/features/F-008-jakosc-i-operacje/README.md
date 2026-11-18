# F-008 · Jakość i operacje

**ID:** `E-001/F-008` · **Status:** `in_progress` · **Epic:** [E-001](../../README.md).

**Wartość:** tester nie jest pierwszą linią wykrywania utraty danych; autor potrafi rozpoznać awarię, zatrzymać rollout i odtworzyć usługę.

## Zakres i akceptacja

- Automatyczne testy auth/sesji/sync, PostgreSQL, Androida i finalnego release, bez uznawania skip za wynik pozytywny.
- Realna matryca Play/device uzupełnia, a nie zastępuje automatyzację.
- Diagnostyka bez danych treści i sekretów, procedura incydentu oraz sprawdzony backup/restore.
- Wyniki A-01…A-24, krytyczne crash/ANR i kontrola regresji nauki/importu z E-002 są jawne.

## Zatwierdzony kierunek i podział

Minimalny koszt, infrastruktura dodatkowa do 50 EUR/miesiąc, RPO 1 h i RTO 24 h od wykrycia, operator-właściciel i e-mail; S24 jako pierwszy fizyczny telefon. Kwoty WARN/HARD AI zostaną ustawione przed startem; dopuszczone ręczne dokupienie i wydatki powyżej WARN, nie ponad HARD. Bez nowego SDK analityki/automatycznych zakupów.

| ID | Task | Status |
|---|---|---|
| E-001/F-008/T-001 | [Bramki CI, PostgreSQL, Android i akceptacja](./tasks/T-001-bramki-jakosci.md), zachowany punkt wejścia B-13 | `in_progress` — etapy 1–2: PostgreSQL i Android w CI |
| E-001/F-008/T-002 | [Środowiska i konfiguracja](./tasks/T-002-srodowiska-i-konfiguracja.md) | `ready` |
| E-001/F-008/T-003 | [Backup, rejestr i odtwarzanie](./tasks/T-003-backup-rejestr-i-odtwarzanie.md) | `ready` |
| E-001/F-008/T-004 | [Monitoring, koszty i incydenty](./tasks/T-004-monitoring-koszty-i-incydenty.md) | `ready` |

Numerów i ścieżek nie zmieniono; dawny duży zakres B-13 ma teraz osobnych właścicieli kontraktów. `ready` oznacza gotowy zakres implementacji po zleceniu, nie istniejące środowisko, opłacone usługi albo osiągnięte RPO.

**Zależności:** testy powstają wraz z implementacją każdego feature'a; końcowa bramka po całym wymaganym P0, przed E-001/F-001/T-002. Brak cyklu „testy dopiero po publikacji”.

**Bramki wykonawcze:** właściwe konta/umowy/region i kosztorys usług, kwoty AI, prywatne klucze/kontakty, realny S24/Play i próba odtworzenia. Nie wymagamy ich zakupu, by przygotować specyfikację; bez potwierdzenia nie ma uruchomienia testerów.

**Weryfikacja:** istniejące `python scripts\ci_check.py` rozszerzone według T-001, wymagane Gradle/release/device oraz izolowany PostgreSQL. **Dowody:** analiza/projekty i decyzje; etap 1 T-001 (PostgreSQL w CI) zweryfikowany lokalnie na prawdziwej bazie, etap 2 (job Android: unit/lint/debug build) lokalnie z JDK 17; oba bez przebiegu GitHub Actions.
