# Vocabulario — raport dla osób decyzyjnych

**Dla kogo:** właściciela produktu, inwestora, osoby z biznesu, księgowości albo administracji. Nie trzeba znać kodu ani czytać prac naukowych.

**Po co ten tekst:** żeby było wiadomo, czego aplikacja już dobrze uczy, czego jej brakuje, co warto budować dalej, za co można brać pieniądze — i czego świadomie nie robić.

**Czego ten tekst nie jest:** instrukcją dla programistów. Szczegóły techniczne są pominięte albo wyjaśnione zwykłym językiem.

**Data:** 23 sierpnia 2026.  
**Podstawa:** przegląd załączonych badań, książki o nauczaniu języków obcych (Macaro, Graham, Woore — znana jest treść pierwszego rozdziału i ośmiu zasad) oraz faktyczny stan aplikacji Vocabulario.

---

## 1. Wniosek w jednym akapicie

Vocabulario dobrze robi jedną, trudną rzecz: pomaga **zapamiętać słowo na długo** i pokazuje je **w bogatym kontekście** (znaczenia, zdania, synonimy, odmiana). Tego nie robi większość darmowych kursów, które udają naukę punktami i seriami dni.

Tego jeszcze nie robi: nie prowadzi użytkownika od „znam tłumaczenie” do **„umiem to słowo przeczytać, usłyszeć, wstawić we frazę i powiedzieć”**. Dopóki tej pętli nie domkniemy, aplikacja jest bardzo dobrym słownikiem z powtórkami — a nie pełnym narzędziem do nauki języka.

**Szansa rynkowa i uczciwość wobec ucznia idą tu w tę samą stronę.** Nie trzeba dokładać gier. Trzeba dokładać prawdziwe użycie słów. Za zaawansowane, kosztowne funkcje (na przykład historie pisane pod konkretne słowa danej osoby) można brać abonament. Za samo powtarzanie słówek — nie.

---

## 2. Czym jest Vocabulario dzisiaj

To aplikacja na Androida. Użytkownik wybiera język, którego się uczy, i dodaje słowa. Do każdego słowa system buduje kartę: znaczenia, przykłady na poziomie ucznia, typowe połączenia, synonimy, przeciwieństwa, rodzinę wyrazów, odmianę. Potem aplikacja układa powtórki tak, żeby wracać do słowa wtedy, gdy zaczyna się je zapominać — częściej na początku, rzadziej później.

W ćwiczeniu można: obejrzeć kartę i ocenić, czy się pamięta; wybrać właściwą odpowiedź spośród ośmiu; wpisać słowo samodzielnie. Działa to także bez internetu. Można wgrać własne listy (na przykład z innych programów do fiszek). Nie ma punktów, odznak ani rywalizacji ze znajomymi. Nie ma jeszcze płatnej subskrypcji. Nie ma wersji na iPhone’a ani w przeglądarce.

**Co z tego jest mocne (i trzeba tego nie psuć):**

- Powtórki w rosnących odstępach czasu — to jedna z najlepiej zbadanych metod zapamiętywania.
- Limit nowych słów dziennie (domyślnie dwadzieścia) — chroni przed zarzuceniem się materiałem.
- Bogata karta zamiast suchej pary „słowo = tłumaczenie”.
- Ćwiczenia, w których trzeba **samemu wydobyć słowo z pamięci**, a nie tylko je rozpoznać.
- Brak sztucznych nagród (punkty, ogień serii dni) — to zaleta, nie brak.

**Czego jeszcze nie ma — i to jest prawdziwa luka:**

- Czytania i słuchania **tekstów ułożonych ze słów, których użytkownik się właśnie uczy**.
- Ćwiczenia, w którym trzeba **użyć frazy albo formy gramatycznej**, a nie tylko samego hasła.
- Mówienia i pisania całych zdań.
- Pomocy, gdy ktoś opuści kilka dni i wraca do góry niezałatwionych powtórek.
- Wyjaśnienia na starcie, **dlaczego** dziś pokazuje się te, a nie inne karty.
- Gotowych zestawów słów na początek (ten temat jest odłożony świadomie, dopóki jakość karty nie będzie pewna).

---

## 3. Dwa cele, które ten produkt ma ze sobą pogodzić

**Cel A — żeby aplikacja utrzymała się na rynku.** Ludzie mają do niej wracać. Ma być jasne, za co płacą. Ma się dać o niej opowiedzieć bez wstydu.

**Cel B — żeby naprawdę uczyła.** Nie „zrobione 200 ćwiczeń”, tylko: po miesiącu człowiek **pamięta i umie użyć** więcej słów niż na początku.

Na rynku językowym te cele często się rozjeżdżają. Aplikacje z dużą liczbą użytkowników często nagradzają samo otwieranie programu. Programy dla zapalonych uczniów (klasyczne fiszki) często są surowe, nudne i uczą słowa w oderwaniu od zdania.

**Zasada sita przy każdej nowej funkcji:** zostaje, jeśli (1) wiadomo, *jaki mechanizm uczenia* za nią stoi, (2) da się zmierzyć postęp inaczej niż liczbą kliknięć, (3) nie zastępuje prawdziwej pracy pamięci pustą nagrodą. Jeśli funkcja tylko „wciąga” albo straszy utratą serii — nie wchodzi do rdzenia produktu.

---

## 4. Co z badań da się powiedzieć po ludzku

Poniżej nie ma streszczeń prac. Są wnioski, które wolno przenieść do decyzji o produkcie. Nazwiska są po to, żeby dało się sprawdzić źródło — nie po to, żeby czytać ten raport z bibliografią w ręku.

### 4.1. Powtarzanie w odstępach działa. Życie użytkownika też.

Od ponad stu lat wiadomo, że materiał wraca lepiej, gdy powtarza się go tuż zanim wypadnie z pamięci, a nie „wszystko na raz przed sprawdzianem”. Dlatego Vocabulario ma taki układ powtórek i **nie powinno z niego rezygnować**.

Badanie z zajęć arabskiego na uczelni (Jorgensen, 2024) pokazuje jednak drugą stronę: studenci *wiedzieli*, że metoda jest dobra, a i tak często jej nie robili. Powtórki zajmowały więcej czasu, niż się spodziewali. Po opuszczeniu dnia kolejka na następny dzień puchła. Po kilku dniach przerwy ludzie odpuszczali w ogóle.

**Dla nas:** problem nie brzmi „czy mieć mądre powtórki”, tylko **„jak nie karać kogoś, kto ma weekend, chorobę albo zwykły zły tydzień”**. Jeśli ktoś wraca w poniedziałek i widzi górę kart, aplikacja go traci — i traci też naukę, bo metoda działa tylko wtedy, gdy sesje są regularne.

Potrzebne jest więc: proste wyjaśnienie na starcie; zapowiedź „ile tego będzie jutro, jeśli dziś odrobisz / jeśli dziś odpuścisz”; możliwość odrabiania zaległości **porcjami**, a nie jednym maratonem; po przerwie — najpierw same zaległe powtórki, bez wpychania nowych słów.

### 4.2. Fiszka uczy przypomnienia. Język to też użycie w tekście.

Praca o historiach dopasowanych do powtórek (Kamzela, Lango, Dušek, 2025) mówi wprost to, co wielu uczących się czuje: klasyczna fiszka uczy, żeby **przypomnieć sobie odizolowane słowo**. Nie uczy, jak to słowo żyje w zdaniu. Książki uproszczone dają kontekst, ale rzadko trafiają akurat w te słowa, które *ta osoba* ma dziś powtórzyć.

Ich pomysł: na podstawie słów zaplanowanych na dziś napisać krótką, spójną historię, w której (a) nie ma słów spoza tego, co uczeń już zna, plus kilku nowych, (b) nowe słowo pojawia się kilka razy, (c) program sprawdza, czy tekst naprawdę nie wychodzi poza ten słownik.

To nie był jeszcze test „czy po tygodniu pamięta się więcej”. To był test, czy da się takie teksty w ogóle napisać przyzwoicie. Da się — pod warunkiem, że maszyna nie ma wolnej ręki i ktoś (albo program) sprawdza słownik.

**Dla nas:** to najbardziej obiecująca nowa funkcja. Nie zamiast powtórek, tylko **do nich**. Użytkownik najpierw (albo tuż obok fiszki) czyta tekst ze *swoimi* słowami. Potem i tak je odtwarza z pamięci. To da się sprzedać jako abonament, bo każda taka historia kosztuje wygenerowanie tekstu — i jest czymś, czego zwykłe fiszki nie dają.

### 4.3. Samodyscyplina da się wspierać. Nie punktami, tylko celami.

Dwie prace o samodzielnym uczeniu się online (Zhang, 2024; Hunutlu, 2023) pokazują, że gdy uczeń sam stoi przed ekranem, sukces zależy od tego, czy umie: postawić cel, pilnować czasu, ocenić, czy metoda działa, poprosić o pomoc. Aplikacja albo mu w tym pomaga, albo zostawia go samego z kolejką kart.

**Dla nas:** nie drzewko odznak. Cel tygodnia w zwykłych jednostkach: „dokończ powtórki zaplanowane na dziś”, „piętnaście minut skupienia”. Po sesji jedno pytanie: było za łatwo, za dużo, czy nie wiem, jak tego użyć. Raz w tygodniu: co działało, co zmienić. Przycisk „pokaż to słowo w nowym zdaniu”, gdy ktoś utknął.

To buduje poczucie, że wysiłek ma skutek — a nie że aplikacja „daje cukierka”.

### 4.4. Ruch i gest pomagają czterolatkom. Nie dorosłym w telefonie.

Badanie z przedszkola (Toumpaniari i inni, 2015): dzieci lepiej zapamiętywały nazwy zwierząt, gdy naśladowały ruchy. To nie przenosi się na dorosłą aplikację słownikową. **Nie budujemy mini-gier ruchowych.**

### 4.5. Quiz na projektorze wciąga na zajęciach. Przy codziennym użyciu się zużywa.

Badanie o Kahootcie i podobnych narzędziach na uczelni (Nadarajan i inni, 2024): studenci lubią to na lekcji. Sami autorzy ostrzegają, że przy wielomiesięcznym powtarzaniu „gra” się opatrzy, a nuda przy komputerze idzie w parze ze słabszą nauką.

**Dla nas:** nie konkurujemy z Duolingo w teleturnieju. Wybór spośród odpowiedzi już mamy — jako ćwiczenie pamięci, nie jako ranking znajomych.

### 4.6. Sztuczna inteligencja świetnie pisze karty. Też zmyśla.

Kilka przeglądów o modelach językowych (Mars; Naseem i inni; Kotei; Chang i Bergen) nie jest o nauce hiszpańskiego. Jest o tym, że maszyna dobrze łapie podobieństwo słów i ładnie pisze — oraz że **wymyśla fakty**, jest czuła na sformułowanie pytania i powiela uprzedzenia.

W Vocabulario to ma znaczenie praktyczne: użytkownik **zapamięta błąd na karcie**. Zła glosa, złe zdanie, zła odmiana to nie „drobiazg w wyglądzie”. To szkoda dla nauki.

**Dla nas:** uzupełnianie karty (enrichment) zostaje, ale karta nie powinna trafiać do nauki, zanim treść nie przejdzie sprawdzenia. Użytkownik już może zgłosić błąd — to trzeba utrzymać i wzmocnić. Nie sprzedajemy „rozmowy z nauczycielem-czatem o byle czym”, bo wtedy model łatwo schodzi na manowce.

### 4.7. Osiem zasad z książki o nauczaniu języków

Macaro, Graham i Woore (2015) układają nauczanie wokół **umiejętności**: słuchania, mówienia, czytania, pisania. Słownik i gramatyka mają tym umiejętnościom *służyć*, a nie być celem samym w sobie.

W przełożeniu na aplikację:

| Zasada (sens) | Co Vocabulario już robi | Czego brakuje |
|---------------|-------------------------|---------------|
| Słuchać i czytać język obcy, dopytywać, gdy się nie rozumie | Są przykłady i odsłuchiwanie głosu | Nie ma kroku „zaznacz, czego nie rozumiem” w tekście albo nagraniu |
| Mówić, także z ryzykiem błędu | Nic | Brak ćwiczenia mówienia |
| Ćwiczyć dłuższe, trochę trudniejsze wypowiedzi i dostawać informację zwrotną | Można wpisać samo hasło | Nie ma układania całego zdania |
| Uczyć się gotowych kawałków języka (zwrotów), nie tylko pojedynczych słów | Zwroty są *opisane* na karcie | Nie ma ćwiczenia, w którym trzeba zwrot **odtworzyć** |
| Czytać i słuchać tekstów trochę powyżej komfortu; wiązać literę z dźwiękiem | Są zapis dźwiękowy i głos | Nie ma opowiadania ułożonego ze słów ucznia |
| Widzieć, że konkretna metoda pracy przynosi skutek | Widać, ile kart zostało | Nie widać związku „zastosowałem taką strategię → poszło lepiej” |
| Pisać własnymi, już znanymi słowami | Wpis hasła | To nie jest pisanie |
| **Słownik i tabele służą użyciu, nie odwrotnie** | Bardzo mocna wiedza o haśle | **Pętla użycia nie jest domknięta** |

Ostatni wiersz to sedno. Nie wyrzucamy bogatej karty. Dopinamy do niej czytanie, frazę, ewentualnie zdanie i głos.

---

## 5. Co z tego wynika: kolejność pracy, nie lista marzeń

Poniżej są **tematy do rozpisania na zadania**, w kolejności, w jakiej mają sens. Świadomie nie używamy tu kodów z planu sprintu.

### Najpierw — żeby ludzie w ogóle wytrzymali powtórki

Bez tego każda nowa funkcja tylko doda pracy.

1. **Odrabianie zaległości bez zasypywania.** Jeśli ktoś wraca po przerwie, nie dostaje jednej niekończącej się sesji. Dostaje porcję na dziś, reszta czeka w kolejce.
2. **Zapowiedź obciążenia.** Przed sesją i po niej: „jeśli zrobisz to dziś, jutro będzie mniej więcej tyle; jeśli odpuścisz, jutro będzie więcej”.
3. **Po przerwie najpierw powtórki, nie nowe słowa.**
4. **Wyjaśnienie na starcie.** Jednym ekranem: po co te odstępy, czemu nie warto „zakuwać na zapas”.
5. **Zaufanie do treści karty.** Karta bez przykładów albo z niepewną treścią nie idzie do nauki. Łatwo zgłosić błąd i wrócić do poprzedniej wersji.

**Sukces widać tak:** więcej osób kończy zaplanowane na dany dzień powtórki; mniej osób znika po tygodniu ciszy.

**Pieniądze:** to jest higiena. Ma być w wersji darmowej. Nie sprzedajemy prawa do powtórek.

### Potem — żeby słowo żyło w języku (tu powstaje odróżnienie i abonament)

6. **Krótka historia ze słów na dziś.** Kilkaset słów tekstu, tylko ze słownika ucznia plus hasła z dzisiejszej sesji; nowe hasło kilka razy; po przeczytaniu dwa–trzy pytania *o te słowa*, nie o fabułę. Program sprawdza, czy w tekście nie pojawiły się obce hasła.
7. **Ćwiczenie zwrotu, nie tylko hasła.** Na przykład luka we frazie, która już jest na karcie.
8. **Ćwiczenie odmiany.** Tabela czasów już istnieje. Brakuje pytania „wstaw właściwą formę” bez podglądania tabeli. Szczególnie ważne dla hiszpańskiego, francuskiego, niemieckiego, włoskiego.
9. **Cel tygodnia i krótka samoocena** — jak w punkcie 4.3.

**Sukces widać tak:** słowo pojawia się w tekście i we frazie, nie tylko na rewersie fiszki; ludzie uważają to za użyteczne, nie za dodatek „dla ozdoby”.

**Pieniądze:** historia pisana pod konkretną osobę kosztuje. Darmowo można dać jedną dziennie albo tylko do słów z dzisiejszej powtórki. W abonamencie: więcej tekstów, dłuższe, z nagraniem lektora.

### Później — mówienie, pisanie, mapa

10. **Napisz zdanie** z danym słowem, używając w miarę możliwości słów już znanych.
11. **Powiedz słowo (albo zdanie)** — program sprawdza, *czy padło to hasło*, a nie czy wymowa brzmi jak u osoby, która wychowała się w tym języku. Zła ocena wymowy zrazi ludzi i będzie niesprawiedliwa.
12. **Mapa powiązań** (synonimy, przeciwieństwa, rodzina). Ma służyć do **dodania słowa do nauki albo do powtórki**, nie do oglądania grafu jak plakatu.

### Na końcu — treść na start, inne platformy, nauczyciel

13. **Gotowe zestawy słów** (na poziom i temat) — dopiero gdy jakość karty jest pewna. Zestaw to lista do wyboru, nie wrzucenie dwustu haseł od razu do codziennych powtórek.
14. iPhone, strona w przeglądarce, panel dla nauczyciela — po ustabilizowaniu kosztów generowania treści.

**Zależność, której nie wolno złamać:** historii ze słów dnia nie puszczać, zanim karta jest sprawdzana i zanim zaległości nie da się odrabiać porcjami. Inaczej ktoś dostanie albo błędny tekst, albo opowiadanie na czterdzieści zaległych słów, którego nikt nie przeczyta.

---

## 6. Za co brać pieniądze — i za co nie

**Nie sprzedajemy powtórek.** Układanie powtórek w czasie to podstawa metody. Zamknięcie tego za płatnością byłoby nieuczciwe wobec badań i łatwe do obejścia (ludzie wrócą do darmowych fiszek).

| Co użytkownik dostaje | Wersja bezpłatna | Wersja płatna |
|----------------------|------------------|---------------|
| Powtórki i trzy sposoby ćwiczenia | Tak, w pełni | To samo — jakość powtórek się nie sprzedaje |
| Uzupełnianie karty (enrichment) | Tak, z dziennym limitem | Wyższy limit, szybsza kolejka |
| Historie ze „swoich” słów | Brak albo jedna dziennie | Więcej, dłuższe, z dźwiękiem |
| Ćwiczenie zwrotów i odmiany z danych, które już są na karcie | Tak | Może zostać bezpłatne — mały koszt |
| Mówienie i sprawdzanie zdań | Nie | Tak (to kosztuje rozpoznawanie mowy i sprawdzenie tekstu) |
| Gotowe zestawy słów | Własne listy i import | Zestawy naszych redaktorów — gdy będą gotowe |
| Narzędzia dla nauczyciela | Nie | Ewentualnie później |

**Jak o tym mówić na zewnątrz:** nie „dni z rzędu w aplikacji”. Mówić: **słowa, które spotkałeś w tekście, wstawiłeś we frazę i nadal pamiętasz**. Tego nie obiecuje wiarygodnie Duolingo. Tego nie opakowuje wygodnie sam Anki.

Koszt po stronie firmy to przede wszystkim generowanie treści przez modele językowe. Wspólna pamięć gotowych haseł (żeby nie płacić za to samo słowo sto razy) już jest w architekturze — i tak powinno zostać.

---

## 7. Czego nie robić

1. **Punktów, rankingów, korony, „żyć”.** Wciągają krótko, męczą przy codziennym użyciu, psują obietnicę uczciwej nauki.
2. **Kary za przerwę w serii dni.** Życie wygrywa z kalendarzem. Kara pogłębia górę zaległości.
3. **Czasu „pogadaj o czym chcesz z nauczycielem-czatem”.** Łatwo o błędy i chaos. Mowa ma być oparta na słowach, których ktoś się uczy.
4. **Gier ruchowych i gestów.** Nie dla tej grupy użytkowników.
5. **Sklepu z cudzymi taliami fiszek w starym formacie.** Psuje jakość karty, od której zależy cały produkt.
6. **Osobnych powtórek dla każdej listy**, zanim ogarniemy główną kolejkę. Rozmnoży zaległości.
7. **Quizu w powiadomieniu zamiast sesji.** Powiadomienie może zaprosić do dzisiejszych powtórek. Nie zastąpi ich teleturniejem.

---

## 8. Jak z tego robić zadania dla zespołu

Jedno zadanie = jeden problem ucznia, nie „wdrożyć algorytm”.

Przykład dobrego opisu:

> Osoba ma na dziś osiem słów do powtórki. Chce przeczytać krótki tekst, który tych słów używa, żeby zobaczyć je w zdaniu — zanim oceni, czy je pamięta. W tekście nie ma haseł spoza jej słownika i tej ósemki. Po tekście trzy pytania o te hasła, nie o fabułę.

Przy każdym zadaniu warto dopisać: jak poznamy, że ktoś się **nauczył**, a nie tylko że kliknął; czego świadomie nie robimy; czy to generuje koszt (tekst, głos) i czy idzie do wersji płatnej.

---

## 9. Werdykt

Vocabulario nie jest udawanym kursem. Ma uczciwszy fundament niż większość rynku: mądre powtórki, głęboka karta, ćwiczenie z pamięci, brak fałszywych nagród.

Żeby spełnić oba cele z początku tego dokumentu, kolejny etap to nie „więcej wciągania”. To cztery rzeczy:

1. sprawić, by ludzie **wytrzymali** codzienną kolejkę,
2. sprawić, by słowo **żyło w tekście i we frazie**,
3. sprawić, by użytkownik **widział związek wysiłku ze skutkiem**,
4. **nie uczyć błędów** z niepewnej treści wygenerowanej przez maszynę.

To jest plan produktu. Nie lista ozdób.

---

## 10. Źródła (dla osób, które chcą sprawdzić)

Nie trzeba ich czytać, żeby zrozumieć ten raport.

1. Mars (2022) — przegląd tego, jak komputery zapisują znaczenie słów. *Applied Sciences.*
2. Jorgensen (2024) — powtórki w odstępach na lektoracie arabskiego; trudność z regularnością. *Journal of Language Teaching.*
3. Zhang (2024) — strategie samodzielnej nauki a motywacja i pewność siebie. *BMC Psychology.*
4. Hunutlu (2023) — przegląd samodzielnej nauki języka przez internet. *SiSAL Journal.*
5. Kamzela, Lango, Dušek (2025) — generowanie historii ograniczonych do słownika ucznia. konferencja EMNLP (ścieżka przemysłowa).
6. Toumpaniari i inni (2015) — gest i ruch przy nauce słówek u przedszkolaków. *Educational Psychology Review.*
7. Nadarajan i inni (2024) — odbiór quizów typu Kahoot na zajęciach. *AJELP.*
8. Chang i Bergen (2024) — co modele językowe potrafią, a gdzie zawodzą. *Computational Linguistics.*
9. Naseem i inni (2021) — przegląd sposobów zapisu słów w informatyce. *ACM TALLIP.*
10. Kotei i Thirunavukarasu (2023) — przegląd dużych modeli do języka. *Information.*
11. Macaro, Graham, Woore (2015) — *Improving Foreign Language Teaching* (pierwszy rozdział i osiem zasad).
12. Tabela odmiany łacińskiego czasownika *amo* — tylko przykład paradygmatu, nie badanie.

**Uzupełnienie spoza załączników** (potrzebne do rzetelnej interpretacji, nieudawane jako treść PDF-ów): klasyczne badania nad powtórkami w odstępach; cztery rodzaje ćwiczeń w nauce słownictwa (czytanie i słuchanie ze zrozumieniem, mówienie i pisanie ze zrozumieniem, skupienie na formie, płynność); „wkład ucznia” przy dodawaniu słowa; trudność, która pomaga pamięci; znudzenie się grą przy długim używaniu quizów.
