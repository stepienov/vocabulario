# E-003 · Paczki startowe

**Status:** `parked`. **Alias historyczny:** E-01.  
**Horyzont:** poza E-001, bez decyzji o implementacji.

## Problem i cel biznesowy

Nowy użytkownik musi sam zbudować listę, zanim doświadczy wartości nauki. Chcemy skrócić drogę do pierwszej sensownej sesji przez materiał dopasowany do pary językowej i poziomu, bez zasypania kolejki SRS.

## Zakres do rozstrzygnięcia

Kuratorowane paczki, generowanie ograniczonej listy albo hybrid. Żaden wariant nie został wybrany. Docelowy materiał ma korzystać z istniejących list i formatu karty; nie jest osobnym systemem powtórek.

**Features/taski:** celowo jeszcze nie utworzono. Najpierw decyzja A/B/hybrid, jakość, koszt i pierwszy wycinek. Sam placeholder ekranu nie oznacza gotowości.

## Miary i warunek odblokowania

- Ustalić bazowy czas onboarding → pierwsza powtórka i docelową poprawę przed statusem `ready`; nie wpisujemy wymyślonego progu.
- Wybrać pierwszy język/poziom, limity instalacji i budżet AI.
- Zdefiniować ocenę jakości glos/przykładów/dystraktorów oraz wykluczanie już posiadanych słów.
- Pokazać w AC, że instalacja listy nie dodaje całej paczki naraz do dziennej sesji.
- Po tych decyzjach utworzyć F-001 z mierzalną akceptacją i ewentualnymi taskami.

**Zależności:** jakość kart i gotowość nauki z [E-002](../E-002-szybka-nauka/README.md); decyzja o priorytecie po stabilizacji [E-001](../E-001-google-play-beta/README.md).

**Poza zakresem:** marketplace, upload społeczności, kopiowanie cudzych talii, rozwijanie placeholdera w ciemno, seed produkcyjny bez kontroli jakości.

**Źródło:** [zachowane warianty i ryzyka](./sources/zalozenia-historyczne.md). Dawne instrukcje sprintowe zastępują [zasady epików](../zasady.md).

**Zamknięcie / dowody:** po zatwierdzeniu zakresu i wykazaniu osiągnięcia miar; obecnie brak, temat odłożony.
