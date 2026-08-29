# QA — nauka, karty, lookup

Krótki spis zmian z tej iteracji i jak to sprawdzić na telefonie (PL→ES).

## Co się zmieniło

1. **Żółty pasek w trybie nauki (pisanie)**  
   Literówka / zła odpowiedź: wyśrodkowany blok `✗ wpisane` + `✓ poprawne`.  
   Zaakceptowany synonim L1: jeden zielony wiersz `wpisane – główne znaczenie`.  
   Pasek niższy (mniej paddingu). Długie słowa: wielokropek (synonim max 2 linie).

2. **Synonim nadal zalicza kartę**  
   Wpisanie synonimu z tyłu fiszki (nie głównego glossu) = poprawnie + żółty pasek jak wyżej, nie czerwony błąd.

3. **Scroll i rozwinięcia**  
   Nowa karta zawsze od hasła u góry. Rozwinięta koniugacja / sekcje nie przenoszą się na następną kartę.

4. **Pod hasłem**  
   Brak IPA. Zamiast tego `headword_note` tylko gdy to prawdziwa zmiana tematu, np. `(e>ie)`.

5. **Rodzina wyrazów**  
   Rodzajnik przy pokrewnych jest kopiowany z cytacji (el/la/los…), nie zgadywany z rodzaju.

6. **Lookup**  
   Gdy dwa kandydaci mają to samo krótkie tłumaczenie → dopisek w nawiasie (`słuchawki (nauszne)`).  
   Liczba mnoga w haśle L2 tylko gdy to prawdziwy lemat słownikowy (`los cascos` = słuchawki, nie `el casco`).

7. **Produkcja — 11 haseł (tylko te)**  
   Poprawione pierwsze znaczenie na żywej bazie. Reszta słownika nietknięta.

   | Hasło | Pierwsze znaczenie |
   |---|---|
   | ir | iść |
   | trabajar | pracować |
   | nacer | rodzić się |
   | abrazar | przytulać |
   | el sonar | sonar |
   | la máquina | maszyna |
   | levantarse | wstawać (z łóżka) |
   | ligar | podrywać |
   | alcanzar | osiągać |
   | servir | przydać się |
   | el bienestar | dobrostan |

Punkt 7 widać tylko na **API produkcji** (Railway) po syncu. Reszta (1–6) jest w APK z tego brancha; check odpowiedzi jest lokalny w apce.

---

## Jak wgrać na telefon

Potrzebujesz Androida 8+ i USB (albo APK).

### A. Studio → telefon (najszybciej na UI)

1. Telefon: opcje programisty + **debugowanie USB**. Kabel, zaufaj komputerowi.
2. Otwórz folder `android/` w Android Studio, Gradle Sync.
3. Wybierz podłączony telefon, Run ▶.
4. **API**
   - Żeby zobaczyć **11 haseł z pkt 7**: zbuduj z produkcją (punkt B) albo w Run Configuration podaj `api.base.url` na Railway.
   - Same bannery / scroll / IPA: może iść na lokalny BE (`android/local.properties` → `api.device.host=` IP komputera, lokalny `.\start-backend.ps1`).

### B. APK na produkcję (11 haseł + prawdziwe konto)

Z katalogu `android/`:

```powershell
.\gradlew :app:assembleDebug "-Papi.base.url=https://vocabulario.up.railway.app/api/v1/"
```

APK: `android/app/build/outputs/apk/debug/app-debug.apk`  
Skopiuj na telefon, zezwól na instalację z nieznanych źródeł, zainstaluj. Odinstaluj starą debugówkę, jeśli instalator krzyczy o podpis.

Zaloguj się, poczekaj na sync (Wi‑Fi). Jeśli karty nadal stare: wyjdź z listy i wejdź z powrotem albo zrób pull (apka online).

---

## Checklista na telefonie

Konto z parą **PL → ES**. Tryb nauki = pisanie (nie tylko wybór).

### Żółty pasek

- [ ] Karta z akcentem (np. `la razón`): wpisz `la razon` → pasek żółty, czerwone ✗ + zielone ✓, **na środku**, karta zaliczona.
- [ ] Karta z synonimem L1 na tyłach: wpisz **synonim**, nie główne słowo → zaliczone, pasek `synonim – główny gloss` (zielony tekst).
- [ ] Zła odpowiedź (inne słowo) → ten sam układ co literówka, ale to błąd (karta niezaliczona).
- [ ] Wysokość paska: mało żółtego nad/pod tekstem, tekst czytelny.

### Scroll

- [ ] Nauka / fiszka: zjedź na dół, rozwiń koniugację, przejdź do **następnej** karty → znowu góra (hasło), koniugacja zwinięta.
- [ ] Lista: otwórz kartę, zjedź, zamknij, otwórz inną → znowu od hasła.

### Hasło / IPA / note

- [ ] Pod lematem **nie ma** transkrypcji IPA.
- [ ] Czasownik z wymianą (np. pensar / querer / pensar jeśli masz): pod hasłem `(e>ie)` albo podobne, nie słowo „regular”.

### 11 haseł (tylko prod + sync)

Otwórz kartę (lista albo nauka), sprawdź **pierwsze** znaczenie:

- [ ] ir → iść (nie „działać”)
- [ ] trabajar → pracować
- [ ] nacer → rodzić się
- [ ] abrazar → przytulać
- [ ] el sonar → sonar (nie „dźwięk”)
- [ ] la máquina → maszyna (nie „pojazd”)
- [ ] levantarse → wstawać (z łóżka)
- [ ] ligar → podrywać
- [ ] alcanzar → osiągać
- [ ] servir → przydać się
- [ ] el bienestar → dobrostan (bez średnika)

Jeśli hasła nie ma na koncie: **lookup** tego słowa i dodaj kartę — cache na prod jest już nowy.

### Lookup (nowy backend; na starym Railway może jeszcze nie być)

- [ ] Szukaj `słuchawki` → kandydat `los cascos`, nie `el casco`.
- [ ] Dwa wyniki o tym samym krótkim PL → glossy z nawiasem, nie dwa identyczne.

### Rodzina wyrazów

- [ ] Karta rzeczownika ES: w rodzinie el/la/los/las przy członkach, spójne z hasłem, bez zmyślonych rodzajników.

---

## Gdy coś nie gra

- Stare znaczenia 11 haseł → apka nie na Railway albo brak syncu / stare local Room.
- Brak żółtego paska synonimu → stary APK (nie ta gałąź).
- Lookup bez nawiasów / `el casco` przy słuchawkach → telefon bije w backend bez tej zmiany (wtedy tylko lokalny BE z tego repo).
