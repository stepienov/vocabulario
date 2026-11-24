# Google Play — deklaracje i Data safety (projekt odpowiedzi)

Projekt z 23.11.2026 na podstawie kodu i informacji właściciela, nie pełnego audytu Play Console/produkcji. Właściciel wypełnia formularze i porównuje je z finalnym AAB/backendem w dniu wysyłki. Bez haseł/kont recenzenta w repo.

## Konto, status sprzedawcy i testy

| Temat | Ustalenie | Decyzja/akcja |
|---|---|---|
| Status sprzedawcy/tradera | Google wymaga deklaracji od wszystkich aktywnych kont deweloperskich w odniesieniu do prawa EOG i UK. Istniejące konta mają termin **1.02.2027**; nowe deklarują status przy tworzeniu konta. Przy koncie osobistym tradera Google publicznie pokazuje **adres i telefon kontaktowy**. | Status i formalną deklarację ustala właściciel. Ustalić typ konta oraz adres i telefon do ujawnienia; termin i zakres potwierdzić w Console przed wydaniem |
| Typ konta | Osobiste vs organizacja (organizacja zwykle wymaga D-U-N-S) | Właściciel sprawdza w Console; nie zmieniać typu „dla wygody” |
| Test zamknięty przed produkcją | Dla kont osobistych utworzonych po 13.11.2023 Google wymaga zamkniętego testu z co najmniej 12 testerami, którzy pozostają zapisani nieprzerwanie przez co najmniej 14 dni przed złożeniem wniosku o dostęp do produkcji | Nie dotyczy samego internal track. Zweryfikować spełnienie warunku; wniosek i termin zależą od typu i daty utworzenia konta |
| Nazwa dewelopera | Polityka prywatności i strona usuwania muszą wskazywać nazwę aplikacji lub dewelopera z karty sklepu | Ustawić „Tenedevía” spójnie w Console, dokumentach i `/delete-account` |

## Deklaracje „App content”

| Deklaracja | Odpowiedź projektowa |
|---|---|
| Privacy policy | `https://vocabulario.io/privacy` (HTML, bez logowania, PL/EN/ES) |
| Ads | Brak reklam |
| App access | Wymagane logowanie → instrukcja i konto testowe dla recenzenta tylko w Console |
| Content rating (IARC) | Edukacyjna; treści generowane przez AI i treści użytkownika prywatne, bez komunikacji między użytkownikami — odpowiadać zgodnie z kwestionariuszem |
| Target audience | Wyłącznie 18+; brak elementów skierowanych do dzieci |
| Data safety | Wymagane dla closed/open/production; **ścieżka wyłącznie internal jest zwolniona** |
| Account deletion | Tak, według właściciela ścieżka w aplikacji i `https://vocabulario.io/delete-account` jest włączona. Rzeczywistego usunięcia konta produkcyjnego nie przetestowano; sprawdzić pełny przebieg, także ścieżkę Google, stronę bez logowania, dane usuwane/zachowywane i zgłoszenie do dostawców. Dla ścieżek innych niż wyłącznie internal musi działać i być prawidłowo zadeklarowana |
| Advertising ID | Nie używamy; sprawdzić scalony manifest release (`AD_ID` z bibliotek Google) |
| Government / Financial / Health / News | Nie dotyczy |
| Treści AI (polityka Play) | Zgłaszanie bez opuszczania aplikacji: „Zgłoś treść” — jest |

## Data safety — macierz

**Nie zatwierdzać jeszcze odpowiedzi „nie udostępniamy”.** Wspólny cache może ponownie wykorzystywać wyniki wyszukiwania w obsłudze zapytań innych osób, a zapytania mogą zawierać dane osobowe. Ocenić ten przepływ według definicji Google Play (w tym czy dane użytkownika są udostępniane innemu użytkownikowi) oraz zminimalizować/wyłączyć cache dla danych osobowych. Dostawcy działający w imieniu aplikacji i logowanie inicjowane przez użytkownika nie przesądzają o całej odpowiedzi. Szyfrowanie transmisji i Data safety sprawdzić na finalnym AAB/backendzie. Mechanizm usunięcia jest deklarowany jako dostępny, ale nie został przetestowany na rzeczywistym koncie produkcyjnym.

| Typ danych (Play) | Zbierane | Cel | Wymagane |
|---|---|---|---|
| Personal info › Email address | Tak | Account management, App functionality | Tak |
| Personal info › User IDs (ID konta, Google ID) | Tak | Account management, App functionality, Fraud prevention/security | Tak |
| App activity › In-app search history | Tak (historia wyszukiwań przy koncie) | App functionality | Tak |
| App activity › Other user-generated content (importy, listy, zgłoszenia, notatki korekt) | Tak | App functionality | Nie (opcjonalne funkcje) |
| App activity › Other actions (oceny powtórek, postęp) | Tak | App functionality | Tak |
| App info and performance › Diagnostics (logi serwera 7 dni) | Tak | App functionality, Fraud prevention/security | Tak |
| Device or other IDs | Nie (brak AAID/ANDROID_ID) — potwierdzić; adres IP tylko jako pseudonim HMAC dla limitów | — | — |
| Location, Contacts, Photos, Audio, Health, Financial | Nie | — | — |

Retencja wyszukiwań (30 dni), surowych danych importu (30 dni po zakończeniu), cache (90 dni od ostatniego użycia/zmiany), logów, dostawców i kopii zapasowych jest niejednakowa. TTL wyszukiwań/importów/cache jest zaimplementowany w kodzie; 24.11.2026 nie potwierdzono jego wdrożenia na produkcji. Nie deklarować tych limitów jako gwarancji. Importy mogą pozostawić wyniki/statusy i utworzone fiszki; oddzielny zapis „pokaż więcej” nie ma automatycznego TTL. Wewnętrzne logi aplikacji i metryki nie określają logów Railway ani retencji usługodawców.

Do potwierdzenia przed złożeniem: klasyfikacja ocen powtórek (App interactions vs Other actions), logów platformy hostingowej z adresem IP, współdzielonego cache (czy jest „sharing”), oraz skutek usunięcia konta dla danych u każdego podmiotu przetwarzającego. Dane safety jest zwolnione tylko przy dystrybucji wyłącznie na internal testing track; closed, open i production wymagają aktualnego formularza.
