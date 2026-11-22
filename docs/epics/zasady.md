# Zasady: epic → feature → task

## Struktura i numeracja

```text
docs/
  epics/
    README.md
    zasady.md
    migracja.md
    E-001-google-play-beta/
      README.md
      sources/
        analiza-2026-11-17.md
      features/
        F-004-email-i-hasla/
          README.md
          tasks/
            T-001-haszowanie-hasel.md
            T-002-poczta-i-odzyskiwanie.md
  setup/
  reference/
  testing/
  archive/
```

- **Epic** to problem i rezultat biznesowy, nie zbiór plików technicznych. Numer globalny: `E-001`, `E-002`, ….
- **Feature** to spójna wartość dla użytkownika w ramach epica. Numer lokalny: `F-001`, `F-002`, ….
- **Task** to wykonalny, sprawdzalny krok feature'a. Numer lokalny: `T-001`, `T-002`, ….
- Pełne ID: `E-001/F-004/T-001`. Poza folderem rodzica używamy pełnego ID i linku, nie samego `T-001`.
- Numery mają co najmniej trzy cyfry; po 999 używamy 1000, nie zerujemy licznika. Nowy numer to najwyższy istniejący + 1 w danym zakresie, nigdy „pierwsza luka”.
- Numer i slug ścieżki są **stałe** po zarejestrowaniu. Zmiana tytułu, priorytetu, statusu lub zakończenie nie przenosi dokumentu i nie renumeruje elementów. Numerów nie odzyskujemy po anulowaniu.
- Nie kodujemy statusu, priorytetu ani daty sprintu w nazwie folderu. Kolejność wykonania wynika z zależności, nie numerów.
- Nie tworzymy równoległych katalogów `docs/features/` i `docs/tasks/`. Dzieci są przy rodzicu; mają kontekst bez szukania po całym repo.

## Ile dokumentów

1. Nowy temat zaczynamy od README epica: problem, odbiorca, cel, zakres, miara sukcesu i decyzje.
2. Feature dostaje własny README, kiedy potrafimy nazwać jego rezultat i kryteria akceptacji. Pomysłu bez wybranego wariantu nie rozpisujemy sztucznie na taski.
3. Mały feature można wykonać bez osobnych tasków: kroki i weryfikacja są w jego README. Rozbijamy dopiero, gdy istnieją niezależne kroki, zależności lub różne sesje pracy.
4. Każdy task należy do dokładnie jednego feature'a. Wspólny fundament ma jednego właściciela, a pozostali linkują zależność — bez kopii zadania.
5. Istniejące analizy i instrukcje danego epica trzymamy w jego `sources/`. To dowody i kontekst z daty dokumentu, nie drugi backlog ani aktualny opis produkcji.
6. Instrukcje środowiska, utrzymywane kontrakty referencyjne i scenariusze wielokrotnego użytku zostają w `setup/`, `reference/`, `testing/`. Nie każdy dokument musi być epikiem.
7. `archive/` mieści dawne audyty i instrukcje, które nie są tematami pracy. **Nie przenosimy tam zakończonych epików.**

## Statusy

| Status | Znaczenie |
|---|---|
| `draft` | Problem/rozwiązanie do doprecyzowania; nie gotowe do implementacji |
| `ready` | Zakres, zależności i akceptacja znane; można rozpocząć po zleceniu |
| `in_progress` | Faktycznie realizowane |
| `blocked` | Praca zatrzymana; zapisz konkretną blokadę i sposób odblokowania |
| `verification_required` | Istnieją specyfikacje lub kod, ale brak aktualnego, kompletnego dowodu wykonania |
| `done` | Zakres i kryteria spełnione, dowody weryfikacji zapisane |
| `parked` | Świadomie odłożone, nie wchodzi do bieżącego zakresu |
| `cancelled` | Świadomie zamknięte bez realizacji; zapisz dlaczego |

Status wpisujemy w nagłówku dokumentu; indeks rodzica jest jego skrótem i aktualizujemy oba w tej samej zmianie. Status rodzica nie wynika automatycznie z liczby plików albo merge'a. Feature/epic jest `done` dopiero po integracyjnej akceptacji; odłożone dzieci muszą być jawnie wyłączone z zakresu, z uzasadnieniem.

Przed `ready`: konkretna wartość, zakres i poza zakresem, decyzje, komplet zależności z pełnymi ID, mierzalne AC oraz sposób sprawdzenia. Rozmiar L sam w sobie nie jest błędem, ale przed kodowaniem trzeba sprawdzić, czy wymaga podziału; nie implementujemy całego epica w jednej zmianie.

### Kompletna specyfikacja przed implementacją

Najpierw uzgadniamy i przygotowujemy dokumenty, dopiero na osobne zlecenie implementujemy. Istniejące szkielety zadań nie są gotowymi kontraktami wykonawczymi.

Feature i taski muszą łącznie odpowiadać na wszystkie mające zastosowanie kwestie:

1. **Biznes:** odbiorca, problem, oczekiwany rezultat, zakres i jawne wyłączenia, zatwierdzone decyzje.
2. **Przebiegi:** punkt wejścia, warunki wstępne, ścieżka sukcesu, anulowanie, błędne dane, brak sieci, timeout, restart, ponowienie i równoległe operacje.
3. **UX:** ekrany, akcje, stany ładowania/puste/błędu/sukcesu, komunikaty, nawigacja, dostępność i lokalizacja.
4. **Kontrakty techniczne:** stan obecnego kodu i miejsca integracji, model danych i migracje, API/pola/walidacja/kody błędów, auth/uprawnienia, skutki uboczne i zadania w tle. Konkretne parametry wymagane do implementacji nie mogą pozostać „do ustalenia w kodzie”.
5. **Dane i zgodność:** właściciel danych, retencja/usuwanie, dostawcy, minimalizacja logowania, wymagane dokumenty/zgody; skutki dla istniejących kont, klientów i niewysłanej pracy.
6. **Dostarczenie:** pełne ID zależności, kolejność i zgodność wydań Android/backend, konfiguracja bez sekretów, przygotowanie środowisk, bezpieczna migracja i procedura naprawy.
7. **Akceptacja:** mierzalne AC powiązane z konkretnymi testami automatycznymi/ręcznymi, danymi testowymi, wymaganym środowiskiem i dowodem wyniku.

Nie dotyczy — wpisujemy z krótkim powodem; wspólny kontrakt — linkujemy zamiast kopiować. Wykonawca bada kod i proponuje rozwiązanie techniczne, właściciel rozstrzyga zachowanie produktu, koszty i zobowiązania. Nie oczekujemy od właściciela wyboru bibliotek czy SQL.

Każda istotna niewiadoma ma pytanie, właściciela i wskazane blokowane zadanie. Nierozstrzygnięte decyzje blokujące implementację oznaczają nadal `draft`/`blocked`, nie `ready`. Nie trzeba zamrażać wszystkich epików naraz: kompletny ma być wdrażany feature wraz z wymaganymi kontraktami jego zależności. Zmiana zatwierdzonego zachowania wymaga aktualizacji i ponownego uzgodnienia specyfikacji, nie cichej decyzji podczas kodowania.

Przed `done`: wynik każdego AC, wykonane testy z wersją kodu/builda i środowiskiem, pozostałe ograniczenia. Pominięty test, opis lub istniejący kod nie są dowodem. Gdy wymagany jest telefon/Play/PostgreSQL i nie ma wyniku, pozostaje `verification_required` albo `blocked`.

## Minimalna zawartość

### Epic — README

- ID, status, priorytet/horyzont.
- Problem biznesowy, odbiorcy i oczekiwany rezultat.
- Miary sukcesu z progiem albo jawna decyzja, jak próg ustalić przed `ready`.
- Zakres i poza zakresem.
- Tabela feature'ów z linkami i statusami.
- Zależności, decyzje, ryzyka; kryterium zamknięcia i dowody.

### Feature — README

- Pełne ID, status, link do epica.
- Problem użytkownika i rezultat.
- Zakres / poza zakresem, kryteria akceptacji.
- Zależności oraz linki do tasków, jeśli potrzebne.
- Weryfikacja, otwarte decyzje i dowody ukończenia.

### Task — plik T-NNN

- Pełne ID, status, priorytet, link do feature'a.
- Cel, konkretny zakres, poza zakresem.
- Zależności: rozróżnij warunek rozpoczęcia, integracji i końcowej akceptacji. Nie twórz cyklu, gdy UI można rozwijać przed końcowym buildem.
- Sprawdzalne kryteria ukończenia i dobrane testy.
- Źródła/ustalenia oraz wynik weryfikacji. Nie kopiuj pełnej analizy do każdego taska.

## Zasady dla istniejących materiałów

- Stare `F-01…F-16` oznaczają ustalenia audytu bety, a `B-*` jego backlog. Nie zmieniamy ich znaczenia na nowe features.
- Dawne „task 00–12” w zachowanych kontraktach to aliasy źródłowe. [Mapa migracji](./migracja.md) jednoznacznie wskazuje pełne ID.
- Stare E-01 z paczkami jest aliasem E-003. Nie ma drugiego aktywnego rejestru.
- Rozbieżność źródła z kodem opisujemy; nie wdrażamy historycznego tekstu w ciemno. Obowiązują bieżące inwarianty produktu, zwłaszcza `learnable`/przykłady/`ready`, limity importu i brak voice/STT.
- Linki aktualizujemy przy migracji. Starych ścieżek nie utrzymujemy jako kolejnych planów ani atrap katalogów.
