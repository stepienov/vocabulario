# F-002 · Wydanie przez Google Play

**ID:** `E-001/F-002` · **Status:** `ready` · **Epic:** [E-001](../../README.md).

**Wartość:** użytkownik instaluje i aktualizuje właściwą aplikację przez Play bez ryzyka utraty niewysłanej pracy.

## Zakres i akceptacja

- Powtarzalny podpisany release AAB, aktualny wymagany SDK, jawny HTTPS i rosnący versionCode.
- Klucze produkcyjne poza Git; debug nie staje się podpisem produkcji.
- Reguły backupu/transferu nie odtwarzają odwołanej sesji ani cudzego cache.
- Migracja debug → Play jest opisana bez sugerowania aktualizacji przez niezgodny podpis.
- Konto deweloperskie i wymagane weryfikacje są gotowe do dystrybucji; właściciel potwierdza faktyczny typ konta i komunikaty Console bez publikowania dokumentów/tożsamości w repo.

| ID | Task | Status |
|---|---|---|
| E-001/F-002/T-001 | [Release i aktualizacja](./tasks/T-001-release-i-aktualizacja.md), B-01 | `ready` |
| E-001/F-002/T-002 | [Gotowość Play Console](./tasks/T-002-konfiguracja-play-console.md) | `ready` |

**Zależności:** T-002 i decyzje ochrony danych przed dystrybucją; samo przygotowanie buildu T-001 może postępować niezależnie. Test bezpieczeństwa migracji razem z E-001/F-003/T-002.

## Uzgodnienia i pozostałe fakty wykonawcze

- Internal → closed, bez publicznej premiery E-001; 5–30 dorosłych. Świat jest celem, rozszerzenie tylko o kraje rzeczywistych testerów po sprawdzeniu obowiązków.
- Właściciel chce **nowy applicationId**, konta/postęp pozostają również po becie. Dotychczasowy debug to inna instalacja, nie in-place update ani powód do resetu danych.
- Konto deweloperskie założone w 2026, prawdopodobnie opłacone; typ/weryfikacje/upload niepotwierdzone. T-002 ma obie procedury, nie przypisuje personal na podstawie daty.
- Nazwa/domena/konkretny identyfikator, realne kontakty, stan Console i kraje to checklista przed uploadem/dystrybucją. Nie są upoważnieniem do kupowania lub klikania Console teraz.

`ready` oznacza opisany zakres i zależności, nie gotowy AAB/zweryfikowane konto. **Poza zakresem:** automatyczny deploy, publiczna premiera i publikacja bez zlecenia. **Weryfikacja:** A-18/A-19, scalony manifest i rzeczywisty artefakt z Play, macierz krajów i potwierdzenia Console. **Dowody:** analiza źródeł/procedura; brak buildu/uploadu/zmiany danych.
