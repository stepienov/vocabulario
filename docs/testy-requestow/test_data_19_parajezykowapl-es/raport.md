# Raport. Para polski–hiszpański

- Data: 8 listopada 2026, 19:38–20:03 UTC
- Profil: interfejs polski, język nauki hiszpański
- Rundy: 6. Przed każdą rundą cache tych haseł był kasowany
- Pierwsze szukanie: co najwyżej jedno pytanie `lookup_draft`
- Drugie pytanie: tylko `lookup_expand` przy „Pokaż więcej” na haśle trasa
- Kierunek „uczę się polskiego”: nieodpalony. Ta strona pary nie przeszła
- Para 2: nieodpalona

Werdykt końcowy: zestaw nie przechodzi. Padają droga, drog, cara, casa i jedno kliknięcie dociągnięcia trasy.

---

## Runda 1. Stan sprzed poprawek

Licznik pytań w tej rundzie był spóźniony (zapis zużycia idzie w tle). Liczba pytań poniżej jest z surowego logu, nie z licznika w pliku rundy.

### droga

- Request: brak. Źródło: leksykon
- Wynik: `la droga / narkotyk`
- Dobrze: rodzajnik jest. Hasło jest hiszpańskie
- Źle: brak drogi. Brak przymiotnika drogi
- Ustalenie: jedno trafienie w leksykonie kończy szukanie. Model nie jest pytany, więc drugie znaczenie nie dochodzi

### drogas

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `el camino / droga`
- Dobrze: droga i narkotyk. Hasła w liczbie pojedynczej
- Źle: nic
- Ustalenie: liczba mnoga schodzi do liczby pojedynczej

### drogie

- Request: `lookup_draft` × 1
- Wynik: `caro / drogi`
- Dobrze: jest drogi. Droga i narkotyk nie weszły (od „droga” są dwie zmiany)
- Źle: nic
- Ustalenie: to hasło spełnia regułę już w rundzie 1

### drogie3

- Request: `lookup_draft` × 1, potem `lookup_expand` × 1. Drugie pytanie puścił skrypt testowy, bo pierwsza lista była pusta. Aplikacja sama by go nie puściła
- Wynik: pusto
- Dobrze: nic
- Źle: brak drogi. Dwa pytania zamiast jednego
- Ustalenie: model dostał „drogie3” i oddał pustą listę. Cyfra nie była obcinana przed pytaniem

### drog

- Request: `lookup_draft` × 1
- Wynik: `el camino / droga`
- Dobrze: jest droga
- Źle: brak narkotyku. Brak drogi
- Ustalenie: model uzupełnił jedną literę do rzeczownika i zatrzymał się na jednym znaczeniu

### somos

- Request: `lookup_draft` × 1
- Wynik: `ser / być`
- Dobrze: jest bezokolicznik i tłumaczenie „być”
- Źle: ocena w pliku rundy jest zła. Skrypt wymagał sera (jedzenie). Tego reguła nie wymaga
- Ustalenie: wynik jest dobry. Poprawiony został skrypt oceny, nie aplikacja

### para

- Request: `lookup_draft` × 1
- Wynik: `para / dla`, `el par / para`
- Dobrze: para i dla. Rzeczownik ma rodzajnik
- Źle: nic
- Ustalenie: homograf wpisu wraca w obu znaczeniach

### cara

- Request: `lookup_draft` × 1
- Surowa odpowiedź: `caro / drogi` oraz `la cara / twarz` z polem `word` = `kara`
- Wynik na liście: samo `caro / drogi`
- Dobrze: jest drogi. Przymiotnik jest w rodzaju męskim
- Źle: brak twarzy. Brak kary
- Ustalenie: twarz była w JSON i została wyrzucona, bo pole `word` nie pasowało do hasła ani do tłumaczenia

### casa

- Request: `lookup_draft` × 1
- Wynik: `la casa / dom`
- Dobrze: jest dom, z rodzajnikiem
- Źle: brak kasy
- Ustalenie: model oddał tylko dokładne słowo. Sąsiada o jedną literę nie było w JSON

### wdoa

- Request: `lookup_draft` × 1
- Wynik: `el agua / woda`
- Dobrze: woda. Droga i narkotyk nie weszły
- Źle: nic
- Ustalenie: zamiana sąsiednich liter jest łapana. Dwie zmiany od „droga” nie wchodzą

### idę

- Request: `lookup_draft` × 1
- Wynik: `ir / iść`
- Dobrze: bezokolicznik w haśle i w tłumaczeniu
- Źle: nic
- Ustalenie: forma osobowa schodzi do bezokolicznika

### trasa, pierwsze szukanie

- Request: `lookup_draft` × 1
- Wynik: `la ruta / trasa`, `el camino / droga`
- Dobrze: jest trasa. Hasło nie jest polskim słowem
- Źle: `el camino / droga` nie jest znaczeniem trasy. Tłumaczenie „droga” jest skopiowane z przykładu w prompcie
- Ustalenie: przykład „droga = camino” wycieka na inne hasło

### trasa, dociągnięcie i cache

- Request po skasowaniu zapisu: `lookup_draft` × 1, wynik `la ruta / trasa`
- Powtórzenie: 0 pytań, ta sama lista
- „Pokaż więcej”: 2, potem 1, 1, 1, potem 0. Lista zamknięta
- Po zamknięciu: 0 pytań, 6 wierszy
- Zapis pl>ru dla „droga”: 0
- Dobrze: powtórzenie nic nie kosztuje. Puste kliknięcie zamyka listę. Inna para nie dostaje tego zapisu
- Źle: kliknięcia 2, 3 i 4 dodały po jednym haśle
- Ustalenie: model oddaje synonimy po jednym. Prompt nie każe oddać kilku naraz

---

## Runda 2

Przed rundą:

- pusty cache zawsze idzie do modelu, leksykon dokleja się do tej odpowiedzi
- cyfra odpada przed pytaniem i przed kluczem cache
- prompt: oddaj każde słowo o jedną zmianę, ze wszystkimi znaczeniami
- dociągnięcie nie sortuje listy od nowa
- skrypt nie woła drugiego pytania, gdy pierwsza lista jest pusta

### droga

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `el camino / droga`
- Dobrze: droga i narkotyk. Jedno pytanie
- Źle: brak drogi
- Ustalenie: leksykon już nie ucina drugiego znaczenia. Przymiotnika model nadal nie oddaje

### drogas

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `el camino / droga`, `la carretera / droga`, `la vía / droga`
- Dobrze: droga i narkotyk, liczba pojedyncza
- Źle: nic
- Ustalenie: bez zmian względem wymagań

### drogie

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `caro / drogi`, `el camino / droga`
- Dobrze: jest drogi
- Źle: droga i narkotyk są o dwie zmiany za daleko
- Ustalenie: nowa reguła w prompcie dodała za dużo. Model nie liczy dwóch zmian

### drogie3

- Request: 0. Źródło: zapis z „drogie”
- Wynik: ten sam co „drogie”
- Dobrze: cyfra nie robi drugiego pytania
- Źle: ten sam błąd co „drogie”, droga i narkotyk
- Ustalenie: obcięcie cyfry działa. Błąd treści jest dziedziczony z „drogie”

### drog

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `el camino / droga`
- Dobrze: droga i narkotyk
- Źle: brak drogi
- Ustalenie: jedna dopisana litera łapie rzeczownik w obu znaczeniach. Przymiotnika nie ma

### somos

- Request: `lookup_draft` × 1
- Wynik: `ser / być`
- Dobrze: być i ser
- Źle: nic
- Ustalenie: bez zmian

### para

- Request: `lookup_draft` × 1
- Wynik: `para / dla`, `el par / para`
- Dobrze: para i dla
- Źle: nic
- Ustalenie: bez zmian

### cara

- Request: `lookup_draft` × 1
- Wynik: `la cara / twarz`
- Dobrze: jest twarz, z rodzajnikiem
- Źle: brak drogi. Brak kary
- Ustalenie: filtr z rundy 1 już nie wyrzuca twarzy. Sąsiadów model nie oddał

### casa

- Request: `lookup_draft` × 1
- Wynik: `la casa / dom`
- Dobrze: jest dom
- Źle: brak kasy
- Ustalenie: bez zmian względem rundy 1

### wdoa

- Request: `lookup_draft` × 1
- Wynik: `el agua / woda`
- Dobrze: woda. Droga i narkotyk nie weszły
- Źle: nic
- Ustalenie: bez zmian

### idę

- Request: `lookup_draft` × 1
- Wynik: `ir / iść`
- Dobrze: bezokolicznik
- Źle: nic
- Ustalenie: bez zmian

### trasa, pierwsze szukanie

- Request: `lookup_draft` × 1
- Wynik: `el trazado / trasa`, `la traza / ślad`
- Dobrze: jest trasa. Polskiego słowa w haśle nie ma
- Źle: nic wymaganego
- Ustalenie: wyciek „camino / droga” z rundy 1 zniknął

### trasa, dociągnięcie i cache

- Request pierwszego szukania po skasowaniu zapisu: licznik 0, lista inna niż przed skasowaniem. Zapis zużycia znowu spóźniony
- Powtórzenie: 0 pytań, ta sama lista
- „Pokaż więcej” 1: `lookup_expand` × 1, dodane 5
- „Pokaż więcej” 2: `lookup_expand` × 1, dodane 0, lista zamknięta
- Po zamknięciu: 0 pytań
- Zapis pl>ru: 0
- Dobrze: kilka haseł naraz. Puste kliknięcie zamyka listę. Inna para bez zapisu
- Źle: po dociągnięciu „la traza” zjechała z drugiej pozycji na koniec
- Ustalenie: sortowanie przy oddawaniu listy nadal przestawia stare wiersze. Zapis kolejności nie jest jeszcze trzymany przy odczycie tej odpowiedzi

---

## Runda 3

Przed rundą: jeśli w odpowiedzi jest słowo o jedną zmianę, wiersz o dwie zmiany odpada. Odmiana, przy której nic nie jest blisko, zostaje.

### droga

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `el camino / droga`
- Dobrze: droga i narkotyk
- Źle: brak drogi
- Ustalenie: filtr dwóch zmian tu nic nie ma do odcięcia. Przymiotnika nie ma w odpowiedzi

### drogas

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `el camino / droga`
- Dobrze: droga i narkotyk
- Źle: nic
- Ustalenie: bez zmian

### drogie

- Request: `lookup_draft` × 1
- Wynik: `el camino / droga`, `caro / drogi`
- Dobrze: jest drogi. Narkotyk odpadł
- Źle: droga nadal jest (dwie zmiany)
- Ustalenie: filtr nie odciął „el camino”, bo pole `word` albo gloss „droga” było liczone jako bliskie

### drogie3

- Request: 0. Zapis z „drogie”
- Wynik: ten sam co „drogie”
- Dobrze: 0 pytań
- Źle: droga nadal jest
- Ustalenie: dziedziczy błąd „drogie”

### drog

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `el camino / droga`
- Dobrze: droga i narkotyk
- Źle: brak drogi
- Ustalenie: bez zmian

### somos

- Request: `lookup_draft` × 1
- Wynik: `ser / być`
- Dobrze: być i ser
- Źle: nic
- Ustalenie: filtr nie wyciął odmiany, bo w tej odpowiedzi nie było bliższego słowa

### para

- Request: `lookup_draft` × 1
- Wynik: `para / dla`, `el par / para`, `la pata / łapa`, `la parra / winorośl`, `la pasa / rodzynek`, `pasar / przechodzić`
- Dobrze: para i dla
- Źle: nic wymaganego. Sąsiedzi o jedną literę są zgodni z regułą
- Ustalenie: model zaczął oddawać sąsiadów, nie tylko sam wpis

### cara

- Request: `lookup_draft` × 1
- Wynik: `la cara / twarz`, `caro / drogi`
- Dobrze: twarz i drogi. Przymiotnik męski
- Źle: brak kary
- Ustalenie: dwa z trzech wymaganych znaczeń są. Kary nie ma na liście

### casa

- Request: `lookup_draft` × 1
- Wynik: `la casa / dom`, `la caza / polowanie`
- Dobrze: jest dom. „caza” jest o jedną literę
- Źle: brak kasy
- Ustalenie: sąsiad hiszpański (s/z) dochodzi. Sąsiad polski (c/k, kasa) nie

### wdoa

- Request: `lookup_draft` × 1
- Wynik: `el agua / woda`
- Dobrze: woda. Droga i narkotyk nie weszły
- Źle: nic
- Ustalenie: bez zmian

### idę

- Request: `lookup_draft` × 1
- Wynik: `ir / iść`
- Dobrze: bezokolicznik
- Źle: nic
- Ustalenie: filtr dwóch zmian tej odmiany nie wyciął

### trasa, pierwsze szukanie

- Request: `lookup_draft` × 1
- Wynik: `el trazado / trasa`, `la tasa / stawka`, `la traza / ślad`, `tras / za`
- Dobrze: jest trasa
- Źle: nic wymaganego
- Ustalenie: doszły słowa o jedną literę. Wymagane tłumaczenie zostało

### trasa, dociągnięcie i cache

- Powtórzenie po pierwszym szukaniu tej części: 0 pytań, ta sama lista
- „Pokaż więcej”: dodane 5, 3, 3, 1, potem 0
- Po zamknięciu: 0 pytań, 14 wierszy, lista zamknięta
- Zapis pl>ru: 0
- Dobrze: pierwsze trzy kliknięcia dodają po kilka haseł. Stare wiersze zostają na górze. Puste kliknięcie zamyka listę
- Źle: czwarte kliknięcie dodało jedno hasło (`la trayectoria`)
- Ustalenie: kilka haseł naraz działa, dopóki model ma ich więcej. Ostatni pojedynczy synonim nadal schodzi osobnym kliknięciem

---

## Runda 4

Przed rundą: z promptu wyszły przykłady homografów. Została sama reguła sąsiada i liter, które brzmią podobnie.

### droga

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`
- Dobrze: jest narkotyk
- Źle: brak drogi. Brak drogi (przymiotnik). Regresja wobec rundy 3
- Ustalenie: bez przykładu model zostawia jedno znaczenie homografu

### drogas

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `el camino / droga`, `la carretera / droga`
- Dobrze: droga i narkotyk
- Źle: nic
- Ustalenie: liczba mnoga nadal trzyma oba znaczenia, choć wpis „droga” już nie

### drogie

- Request: `lookup_draft` × 1
- Wynik: `la drogue / narkotyk`, `la droga / narkotyk`, `caro / drogi`, `el caro / drogi`
- Dobrze: jest drogi
- Źle: narkotyk jest o dwie zmiany za daleko. „drogue” jest z trzeciego języka
- Ustalenie: reguła sąsiada wpuściła francuskie „drogue” (jedna litera od „drogie”)

### drogie3

- Request: 0. Zapis z „drogie”
- Wynik: ten sam co „drogie”
- Dobrze: 0 pytań
- Źle: ten sam narkotyk
- Ustalenie: dziedziczy błąd „drogie”

### drog

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`
- Dobrze: jest narkotyk
- Źle: brak drogi. Brak drogi (przymiotnik). Regresja wobec rundy 3
- Ustalenie: ten sam skutek co przy „droga”. Przykład trzymał drugie znaczenie

### somos

- Request: `lookup_draft` × 1
- Wynik: `ser / być`
- Dobrze: być i ser
- Źle: nic
- Ustalenie: bez zmian

### para

- Request: `lookup_draft` × 1
- Wynik: `para / dla`, `parar / zatrzymywać`
- Dobrze: jest dla
- Źle: brak rzeczownika para (`el par`). Regresja
- Ustalenie: bez przykładu homografu model oddaje przyimek i czasownik, rzeczownik ginie

### cara

- Request: `lookup_draft` × 1
- Wynik: `la cara / twarz`, `la capa / warstwa`, `la cala / zatoka`, `la casa / dom`, `la cana / siwy włos`, `la cama / łóżko`
- Dobrze: jest twarz
- Źle: brak drogi. Brak kary. Regresja drogiego wobec rundy 3
- Ustalenie: limit wierszy zapełnił się rzeczownikami o jedną literę. Przymiotnik i kara nie weszły

### casa

- Request: `lookup_draft` × 1
- Wynik: `la casa / dom`, `casar / żenić`, `la cala / zatoczka`, `la capa / peleryna`, `la caja / pudełko`
- Dobrze: jest dom
- Źle: brak kasy. Ocena w pliku rundy jest zła: skrypt zaliczył „caja” jako kasę, a tłumaczenie to „pudełko”
- Ustalenie: skrypt oceny poprawiony po tej rundzie. Hasło nie przechodzi

### wdoa

- Request: `lookup_draft` × 1
- Wynik: `el agua / woda`
- Dobrze: woda
- Źle: nic
- Ustalenie: bez zmian

### idę

- Request: `lookup_draft` × 1
- Wynik: `ir / iść`
- Dobrze: bezokolicznik
- Źle: nic
- Ustalenie: bez zmian

### trasa, pierwsze szukanie

- Request: `lookup_draft` × 1
- Wynik: `la tasa / stawka`, `la traza / ślad`
- Dobrze: hasła hiszpańskie
- Źle: brak tłumaczenia „trasa”. Regresja
- Ustalenie: model potraktował wpis jako literówkę sąsiadów i pominął samo słowo

### trasa, dociągnięcie i cache

- Pierwsze szukanie tej części: `lookup_draft` × 1, ta sama para wierszy bez „trasa”
- Powtórzenie: 0 pytań
- „Pokaż więcej”: dodane 5, 2, 2, 2, 2, 1. Po szóstym kliknięciu lista jeszcze nie zamknięta (limit kliknięć skryptu)
- Po tym: 0 pytań, 16 wierszy
- Zapis pl>ru: 0
- Dobrze: tłumaczenie „trasa” dochodzi dopiero przy dociągnięciu (`la ruta` i dalej). Powtórzenie jest darmowe
- Źle: pierwsze szukanie wymagania nie spełnia. Ostatnie kliknięcie dodało jedno hasło. Lista nie zdążyła się zamknąć w limicie kliknięć
- Ustalenie: sąsiedzi wypchnęli znaczenie wpisu z pierwszego pytania. Dociągnięcie je przywraca, czyli płacimy drugie pytanie za coś, co miało być w pierwszym

---

## Runda 5

Przed rundą: przykłady homografów wróciły, z dopiskiem że nie są całą odpowiedzią. Pole `word` nie ratuje już wiersza, którego hasło i tłumaczenie są dalej niż o jedną zmianę.

### droga

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `el camino / droga`, `drogar / odurzać narkotykami`
- Dobrze: droga i narkotyk wróciły
- Źle: brak drogi
- Ustalenie: przykład przywraca homograf. Przymiotnika nadal nie ma. „drogar” jest o jedną literę i regule nie przeczy

### drogas

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `el camino / droga`
- Dobrze: droga i narkotyk
- Źle: nic
- Ustalenie: bez zmian

### drogie

- Request: `lookup_draft` × 1
- Surowa odpowiedź miała też `el camino / droga` i `la droga / narkotyk`
- Wynik na liście: `caro / drogi`, `costoso / drogi`
- Dobrze: tylko drogi. Droga i narkotyk odcięte
- Źle: nic
- Ustalenie: filtr dwóch zmian działa, gdy bliższe słowo (drogi) już jest na liście

### drogie3

- Request: 0. Zapis z „drogie”
- Wynik: `caro / drogi`, `costoso / drogi`
- Dobrze: to samo co „drogie”, 0 pytań
- Źle: nic
- Ustalenie: hasło przechodzi

### drog

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `el camino / droga`, `la carretera / droga`
- Dobrze: droga i narkotyk
- Źle: brak drogi
- Ustalenie: przykład przywrócił rzeczownik. Przymiotnika model nie dodał

### somos

- Request: `lookup_draft` × 1
- Surowa odpowiedź: `ser / być` oraz kilka rzeczowników (`el som`, `la soma`, `el domo`, `la somos / suma` i inne)
- Wynik na liście: `la somos / suma`
- Dobrze: nic
- Źle: brak być. Brak ser. Regresja
- Ustalenie: filtr wyrzucił czasownik, bo „la somos” ma zero zmian od wpisu, a „ser” jest dalej niż o jedną literę. Odmiana ginie, gdy obok stoi jakiekolwiek bliższe słowo

### para

- Request: `lookup_draft` × 1
- Wynik: `para / dla`, `el par / para`, `parar / zatrzymywać`
- Dobrze: para i dla wróciły
- Źle: nic
- Ustalenie: przykład homografu przywraca rzeczownik, który runda 4 zgubiła

### cara

- Request: `lookup_draft` × 1
- Surowa odpowiedź miała też wiersz `cara / kara` bez rodzajnika
- Wynik na liście: `la cara / twarz`, `la capa / warstwa`, `la cala / zatoka`, `caro / drogi`, `la cama / łóżko`, `la casa / dom`
- Dobrze: twarz i drogi
- Źle: kary na liście nie ma
- Ustalenie: kara była w JSON na haśle bez rodzajnika. Rzeczownik hiszpański bez rodzajnika jest usuwany

### casa

- Request: `lookup_draft` × 1
- Wynik: `la casa / dom`, `casar / żenić`, `la caza / polowanie`
- Dobrze: jest dom
- Źle: brak kasy
- Ustalenie: w tej surowej odpowiedzi wiersza „kasa” nie było

### wdoa

- Request: `lookup_draft` × 1
- Surowa odpowiedź miała też `boda`, `moda`, `oda`. Na liście ich nie ma
- Wynik: `el agua / woda`
- Dobrze: woda. Słowa dalej niż o jedną zmianę odcięte
- Źle: nic
- Ustalenie: filtr sąsiada odcina obce wyrazy, gdy właściwe słowo jest blisko

### idę

- Request: `lookup_draft` × 1
- Wynik: `ir / iść`
- Dobrze: bezokolicznik
- Źle: nic
- Ustalenie: bez zmian

### trasa, pierwsze szukanie

- Request: `lookup_draft` × 1
- Wynik: `el trayecto / trasa`, `la ruta / trasa`
- Dobrze: trasa jest od pierwszego pytania. Hasła hiszpańskie
- Źle: nic
- Ustalenie: powrót przykładów przywrócił znaczenie wpisu, które runda 4 wypchnęła

### trasa, dociągnięcie i cache

- Pierwsze szukanie tej części: `lookup_draft` × 1, 4 wiersze, w tym trasa
- Powtórzenie: 0 pytań, ta sama lista
- „Pokaż więcej”: dodane 3, 5, potem 0. Lista zamknięta
- Po zamknięciu: 0 pytań, 12 wierszy
- Zapis pl>ru: 0
- Dobrze: kilka haseł naraz, stare na górze, puste kliknięcie zamyka, powtórzenie darmowe, inna para bez zapisu
- Źle: nic
- Ustalenie: ta część procedur dociągnięcia w tej rundzie przechodzi

---

## Runda 6

Przed rundą: czasownik nazwany formą słownikową zostaje, nawet gdy obok jest słowo o jedną zmianę.

Po rundzie, bez nowego pytania do modelu: wiersz, w którym hasło i tłumaczenie są tym samym wpisem, jest wyrzucany zanim kod zmieni końcówkę `-a` na `-o`.

### droga

- Request: `lookup_draft` × 1
- Surowa odpowiedź: `el camino / droga`, `la droga / narkotyk`, `droga / droga` (przymiotnik), `la draga / pogłębiarka`
- Wynik na liście: `la droga / narkotyk`, `el camino / droga`, `drogo / drogi`, `la draga / pogłębiarka`
- Dobrze: droga i narkotyk
- Źle: „drogo / drogi” nie pochodzi od modelu. Kod zamienił echo „droga / droga” na hiszpańską końcówkę i ściągnął tłumaczenie do „drogi”. Test zaliczył przymiotnik, którego nie było
- Ustalenie: zaliczenie jest fałszywe. Po poprawce ten wiersz odpada. „caro” w JSON nie było, więc przy powtórce hasło znowu nie przejdzie

### drogas

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `el camino / droga`
- Dobrze: droga i narkotyk
- Źle: nic
- Ustalenie: bez zmian

### drogie

- Request: `lookup_draft` × 1
- Surowa odpowiedź miała też drogę i narkotyk. Filtr je odciął
- Wynik: `caro / drogi`, `querido / drogi`
- Dobrze: tylko drogi
- Źle: nic
- Ustalenie: bez zmian względem rundy 5

### drogie3

- Request: 0. Zapis z „drogie”
- Wynik: `caro / drogi`, `querido / drogi`
- Dobrze: 0 pytań, ta sama treść
- Źle: nic
- Ustalenie: bez zmian

### drog

- Request: `lookup_draft` × 1
- Wynik: `la droga / narkotyk`, `el camino / droga`
- Dobrze: droga i narkotyk
- Źle: brak drogi
- Ustalenie: w JSON nie ma wiersza z przymiotnikiem. To nie filtr

### somos

- Request: `lookup_draft` × 1
- Wynik: `el somo / som`, `ser / być`
- Dobrze: być i ser wróciły
- Źle: nic wymaganego. „somo” jest o jedną literę
- Ustalenie: poprawka filtra z tej rundy przywraca czasownik wycięty w rundzie 5

### para

- Request: `lookup_draft` × 1
- Wynik: `para / dla`, `el par / para`, `la pala / łopata`, `parar / zatrzymywać`, `la parra / winorośl`, `la vara / kij`
- Dobrze: para i dla
- Źle: nic wymaganego
- Ustalenie: bez zmian

### cara

- Request: `lookup_draft` × 1
- Surowa odpowiedź, wiersz kary: hasło `cara` bez rodzajnika, tłumaczenie `kara`
- Wynik na liście: `la cara / twarz`, `la capa / warstwa`, `caro / drogi`, `la cama / łóżko`, `la casa / dom`, `la caza / polowanie`
- Dobrze: twarz i drogi
- Źle: kary na liście nie ma
- Ustalenie: model oddaje karę jako tłumaczenie wpisu, nie jako hiszpańskie hasło z rodzajnikiem. Filtr rodzajnika ten wiersz usuwa. Przepuszczenie go też byłoby błędem, bo hasłem zostałby wpis

### casa

- Request: `lookup_draft` × 1
- Surowa odpowiedź, wiersz kasy: hasło `casa` bez rodzajnika, tłumaczenie `kasa`
- Wynik na liście: `la casa / dom`, `casar / żenić`, `la caza / polowanie`
- Dobrze: jest dom
- Źle: kasy na liście nie ma
- Ustalenie: ten sam mechanizm co przy karze. Tłumaczenie jest. Hasło języka nauki nie

### wdoa

- Request: `lookup_draft` × 1
- Wynik: `el agua / woda`
- Dobrze: woda
- Źle: nic
- Ustalenie: bez zmian

### idę

- Request: `lookup_draft` × 1
- Wynik: `ir / iść`
- Dobrze: bezokolicznik
- Źle: nic
- Ustalenie: bez zmian

### trasa, pierwsze szukanie

- Request: `lookup_draft` × 1
- Wynik: `el trayecto / trasa`, `la ruta / trasa`
- Dobrze: trasa, hasła hiszpańskie
- Źle: nic
- Ustalenie: bez zmian

### trasa, dociągnięcie i cache

- Pierwsze szukanie tej części: `lookup_draft` × 1, 5 wierszy, trasa jest
- Powtórzenie: 0 pytań, ta sama lista
- „Pokaż więcej”: dodane 4, 6, 1 (`la línea`), potem 0. Lista zamknięta
- Po zamknięciu: 0 pytań, 16 wierszy
- Zapis pl>ru: 0
- Dobrze: kilka haseł na dwóch pierwszych kliknięciach. Stare wiersze na górze. Puste kliknięcie zamyka listę. Powtórzenie darmowe. Inna para bez zapisu
- Źle: trzecie kliknięcie dodało jedno hasło
- Ustalenie: ten sam wzorzec co w rundzie 3. Ostatni synonim schodzi osobno

---

## Ustalenia po sześciu rundach

- Leksykon z jednym znaczeniem nie może kończyć szukania. Od rundy 2 pierwsze pytanie idzie do modelu.
- Cyfra na końcu nie jest osobnym hasłem. „drogie3” bierze zapis „drogie”.
- Słowo o dwie zmiany da się odciąć w kodzie, gdy bliższe już jest. Odmiana czasownika musi przy tym zostać. Runda 5 tego nie robiła, runda 6 tak.
- Przykładów homografów nie wolno usuwać. Runda 4 zgubiła drogę, „el par” i tłumaczenie trasy.
- Sam przykład ucina odpowiedź na wypisanych znaczeniach. Przymiotnik przy „droga” i „drog” nadal nie przychodzi.
- „kara” i „kasa” przychodzą jako tłumaczenie dopisane do wpisu, bez rodzajnika. Filtr je wyrzuca. To nie jest brak znaczenia w JSON. To złe hasło.
- Echo „droga / droga” nie może być przerabiane na „drogo / drogi”. Zaliczenie drogi w rundzie 6 jest nieważne.
- Dociągnięcie umie dodać kilka haseł i zamknąć listę. Ostatnie kliknięcie nadal potrafi dodać jeden synonim.
- Zapis pl>es nie powstaje dla pl>ru. Sprawdzone w każdej rundzie.
