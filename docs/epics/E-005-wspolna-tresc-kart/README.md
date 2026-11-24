# E-005 · Wspólna treść kart

**Status:** `in_progress` · **Priorytet:** do decyzji · **Odbiorca:** każdy użytkownik dodający lub uczący się słów.

## Problem i rezultat

Pełna treść tej samej karty może istnieć we wspólnym słowniku i w wielu kartach użytkowników. Zajmuje to miejsce, utrudnia aktualizacje i dopuszcza rozbieżności. Celem jest jedno autorytatywne źródło wspólnej treści dla ustalonej tożsamości słowa i pary języków. Użytkownicy nadal mają własne karty, listy i niezależny postęp; telefon zachowuje kopię potrzebną offline.

Pierwszy etap nie oznacza zakończenia migracji historycznych kart ani całego E-005. E-005 nie wznawia historycznych zadań E-002 i nie zmienia obecnego priorytetu E-001.

## Features

| ID | Rezultat | Status |
|---|---|---|
| E-005/F-001 | [Jedna wspólna treść i bezpieczna migracja](./features/F-001-wspolna-tresc/README.md) | `in_progress` |

## Granice i miary

- Po migracji każda rozstrzygnięta tożsamość ma dokładnie jedną autorytatywną bieżącą treść; indywidualne rekordy nie zawierają jej kolejnej pełnej kopii. Nierozstrzygnięte przypadki blokują końcowe przełączenie.
- Zmiana wspólnej treści dociera do wszystkich użytkowników, bez utraty postępu i pracy offline. Przedpremierowe aplikacje nie wymagają bezterminowego wsparcia; granicę zgodności wydanych wersji ustala E-001/F-002.
- Wyjątek od zachowania postępu: gdy ręcznie zatwierdzona poprawka naprawia błąd wpływający na naukę, postęp tej karty wraca do początku u wszystkich jej posiadaczy. Historia i inne karty pozostają; zmiany niemające wpływu na naukę nie resetują postępu.
- Gotowe wspólne wpisy zachowujemy i utrzymujemy również po usunięciu ostatniej karty użytkownika, aby ponownie wykorzystywać już pozyskaną treść i ograniczać wywołania AI, z uwzględnieniem prywatności i prawa.
- Wyszukiwanie i dodawanie powinny korzystać z wystarczających danych w PostgreSQL przed kolejnym wywołaniem AI. Spadek kosztów mierzymy; nie zakładamy, że sam wzrost słownika wyeliminuje wszystkie rodzaje requestów.
- Oszczędność jest mierzona przed i po w porównywalnym środowisku: dane, TOAST, indeksy, WAL, backup, wydajność i koszty zapytań; sama suma długości JSON nie jest oszczędnością dysku. Progi wydajności i kosztów wymagają zatwierdzenia przed `ready`.
- Poza zakresem: łączenie kafelków wyszukiwania, zmiana nauki/importu, kasowanie historii dla samej oszczędności i przebudowa offline od zera.

## Zależności i zamknięcie

Obowiązują kontrakty [E-002/F-004](../E-002-szybka-nauka/features/F-004-karty/README.md), [E-002/F-005](../E-002-szybka-nauka/features/F-005-import/README.md) oraz [E-001/F-003/T-003](../E-001-google-play-beta/features/F-003-sesja-i-offline/tasks/T-003-wynik-synchronizacji.md). Retencja i zgodność wersji wymagają uzgodnienia z E-001/F-007 oraz E-001/F-002. Dowody ukończenia: brak.
