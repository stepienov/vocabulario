# Testy requestów wyszukiwania

Ten katalog mówi, jak ma działać szukanie i które przypadki mają je podważyć. Nie jest opisem dzisiejszego kodu.

Języków interfejsu jest szesnaście i języków nauki jest szesnaście. To ta sama lista. Par do opłacenia jest dziesięć. Każde pytanie do modelu kosztuje, więc nie ma tu iloczynu 16 × 15.

## Co ma wrócić

Użytkownik ma dostać każde słowo z pary, które odpowiada wpisowi. Słowo odpowiada wpisowi, gdy zachodzi choć jedno z tego:

- jest tym wpisem;
- jest formą, którą jeden z języków pary naprawdę od tego słowa tworzy;
- od wpisu dzieli je dokładnie jedna różnica: jeden znak zmieniony, jeden znak za dużo, jeden znak za mało albo dwa sąsiednie znaki zamienione miejscami.

Znak spoza pisma odpada przed porównaniem. „droga3” porównuje się tak jak „droga”.

Słowo, które odpowiada, wchodzi ze wszystkimi swoimi znaczeniami w tej parze. „cars” jest liczbą mnogą angielskiego samochodu i jest „car” z jedną literą za dużo. „car” znaczy samochód i ponieważ, więc wracają oba.

Dwie różnice naraz już nie odpowiadają. „faster” od „fast” dzielą dwa znaki, więc niemieckie „prawie” przy „faster” nie wchodzi. To jest granica reguły, nie wyjątek dla jednego słowa.

Reszta działania:

1. Pierwsze szukanie hasła to jedno pytanie do modelu. Drugie pytanie o to samo hasło idzie dopiero po kliknięciu „Pokaż więcej”.
2. Użytkownik nie oznajmia, w którym z dwóch języków pary pisze. Wpis sprawdza się w obu. Para jest jedna, bez osobnego zestawu „w drugą stronę”. Znaczenia nie zależą od tego, który język wpisano. Od języka nauki zależy tylko to, który język stoi w haśle.
3. Na górze są wiersze, w których wpis zgadza się z hasłem albo z tłumaczeniem. Reszta stoi pod nimi. Dociągnięte wiersze dochodzą na końcu.
4. „Pokaż więcej” dopisuje kilka nowych haseł naraz. Jedno nowe hasło na kliknięcie jest błędem. Lista kończy się, gdy kliknięcie nie doda nic.
5. Hasło jest formą słownikową języka nauki. Tłumaczenie jest formą słownikową języka interfejsu. Fałszywe jest hasło będące słowem języka interfejsu, a nie hasłem języka nauki. Tłumaczenie w języku interfejsu fałszem nie jest. Fałszem jest opis gramatyki zamiast tłumaczenia i hasło bez związku z wpisem.
6. Rzeczownik ma rodzajnik wtedy, gdy język nauki stawia rodzajnik przy haśle: hiszpański, francuski, niemiecki, włoski, portugalski. Nie ma rodzajnika, gdy język nauki go przy haśle nie stawia: polski, angielski, rosyjski, chiński. Brak rodzajnika tam, gdzie ma być, i rodzajnik tam, gdzie go być nie ma, są błędem.
7. Wynik z jednej pary nie świadczy o pozostałych. Zapis cache jednej pary nie może obsłużyć innej pary.

Pusty wynik jest błędem, jeśli jakiekolwiek słowo pary odpowiada wpisowi. Brak któregoś odpowiadającego słowa jest błędem. Brak dalszego synonimu, który od wpisu dzieli więcej niż jedna różnica, błędem nie jest.

## Dociąganie i cache

To jest osobny przebieg, na jednym haśle z tabeli pary, oznaczonym niżej. Przed startem usuwa się zapis tego hasła dla tej pary. Liczy się wywołania modelu.

1. Pierwsze szukanie. Jedno wywołanie. Wiersze są zapisane w cache tej pary. Rzeczowniki mają rodzajnik albo go nie mają, zgodnie z językiem nauki.
2. To samo hasło jeszcze raz. Zero wywołań. Wiersze są te same, w tej samej kolejności.
3. „Pokaż więcej”. Jedno wywołanie. Kilka nowych haseł dochodzi na końcu. Stare wiersze zostają na górze i nie znikają. Cache dostaje pełną listę.
4. To samo hasło trzeci raz. Zero wywołań. Widać listę sprzed dociągnięcia i hasła dociągnięte.
5. „Pokaż więcej”, aż kliknięcie nic nie doda. Cache zapisuje, że lista jest zamknięta.
6. To samo hasło jeszcze raz. Zero wywołań. Lista zamknięta, bez nowego pytania.
7. To samo hasło w innej parze, tam gdzie tabela tego wymaga. Nie wolno oddać zapisu z kroku 1.

## Pary

Kolumna „musi być” wynika z reguły powyżej, nie z osobnej decyzji przy każdym słowie. „Dalej niż jedna różnica” oznacza słowo, które przy tym wpisie jest błędem, bo reguła go nie obejmuje.

### polski i hiszpański

Rodzajnik jest wymagany, gdy językiem nauki jest hiszpański. Gdy językiem nauki jest polski, rodzajnik przy haśle jest błędem. Dociąganie i cache: „trasa”. Inna para: „droga” przy polskim i rosyjskim nie może wziąć tego zapisu.

| Wpis | Musi być | Dalej niż jedna różnica |
|---|---|---|
| droga | droga, narkotyk i drogi, bo „drogi” dzieli od „droga” jeden znak | — |
| drogas | droga i narkotyk. Hasło w liczbie pojedynczej | — |
| drogie | drogi. Jest „drogi” z jedną literą za dużo | droga i narkotyk, bo od „droga” dzielą je dwie zmiany |
| drogie3 | to, co przy „drogie” | pusto |
| drog | droga, narkotyk i drogi. Do każdego brakuje jednego znaku | — |
| somos | być i ser. To forma czasownika „ser” | — |
| para | para i dla | — |
| cara | twarz, drogi i kara | rodzaj żeński jako hasło przymiotnika |
| casa | dom i kasa | — |
| wdoa | woda | droga i narkotyk |
| idę | iść | forma osobowa w haśle albo w tłumaczeniu |
| trasa | trasa | polskie słowo jako hasło hiszpańskie |

### polski i angielski

Żaden z tych języków nie stawia rodzajnika przy haśle. Rodzajnik przy „dog” albo „pies” jest błędem. Dociąganie i cache: „list”.

| Wpis | Musi być | Dalej niż jedna różnica |
|---|---|---|
| list | list i lista | — |
| lists | list i lista | — |
| list3 | list i lista | pusto |
| pies | pies i ciasto. „pies” jest „pie” z jedną literą za dużo | — |
| pie | ciasto i pies | — |
| brat | brat i bachor | — |
| brats | brat i bachor | — |
| pan | pan i patelnia | — |
| pans | pan i patelnia | — |
| freind | przyjaciel | list |
| went | iść | forma czasu przeszłego w haśle |
| dog | pies, bez rodzajnika | „the dog” albo „el dog” |

### polski i niemiecki

Rodzajnik jest wymagany, gdy językiem nauki jest niemiecki. Po polsku rodzajnika przy haśle nie ma. Niemiecki rzeczownik w haśle zaczyna się wielką literą. Dociąganie i cache: „dom”. Inna para: „gift” stąd nie wchodzi, bo prezent i trucizna należą do niemieckiego z angielskim.

| Wpis | Musi być | Dalej niż jedna różnica |
|---|---|---|
| grad | grad i stopień | — |
| Grade | grad i stopień. Jedna litera za dużo przy „grad” | — |
| grad3 | grad i stopień | pusto |
| gradzie | grad i stopień. To forma słowa „grad” | — |
| los | los i „ruszaj” albo kupon | — |
| tor | tor i brama | — |
| Tore | tor i brama | angielskie „tore” |
| ale | ale i wszyscy | — |
| alle | ale i wszyscy | — |
| Hund | pies, z rodzajnikiem, wielką literą | rzeczownik małą literą albo bez rodzajnika |

### niemiecki i angielski

Rodzajnik tylko wtedy, gdy językiem nauki jest niemiecki. Dociąganie i cache: „Hund”.

| Wpis | Musi być | Dalej niż jedna różnica |
|---|---|---|
| gift | prezent i trucizna | — |
| Gift | prezent i trucizna | — |
| gifts | prezent i trucizna | — |
| gift3 | prezent i trucizna | pusto |
| fast | szybko i prawie | — |
| faster | szybko. To forma angielskiego „fast” | prawie. Dzielą je dwa znaki, nie jeden |
| hell | piekło i jasny | — |
| Hunde | pies | trucizna |

### francuski i angielski

Rodzajnik tylko wtedy, gdy językiem nauki jest francuski. Dociąganie i cache: „maison”.

| Wpis | Musi być | Dalej niż jedna różnica |
|---|---|---|
| car | samochód i ponieważ | — |
| cars | samochód i ponieważ | — |
| car3 | samochód i ponieważ | pusto |
| chat | czat i kot | — |
| chats | czat i kot | — |
| son | syn i zaimek dzierżawczy | — |
| sons | syn i zaimek dzierżawczy | — |
| voituer | samochód. Jedno przestawienie w „voiture” | ponieważ. Od „car” dzieli go więcej niż jeden znak |
| maison | dom, z rodzajnikiem, gdy językiem nauki jest francuski | kot |

### włoski i angielski

Rodzajnik tylko wtedy, gdy językiem nauki jest włoski. Dociąganie i cache: „casa”.

| Wpis | Musi być | Dalej niż jedna różnica |
|---|---|---|
| cane | laska i pies | — |
| cani | laska i pies. Jeden znak zmieniony wobec „cane” | — |
| canes | laska i pies | — |
| cane3 | laska i pies | pusto |
| sale | wyprzedaż i sól | — |
| sales | wyprzedaż i sól | — |
| male | mężczyzna i zły | — |
| casa | dom oraz przypadek albo walizka | — |
| case | dom oraz przypadek albo walizka | — |

### portugalski brazylijski i portugalski europejski

Rodzajnik jest wymagany przy obu ustawieniach, bo oba warianty stawiają rodzajnik przy haśle. Hasło ma być w tym wariancie, który jest językiem nauki, a nie kopią drugiego. Dociąganie i cache: „casa”.

| Wpis | Musi być | Dalej niż jedna różnica |
|---|---|---|
| apelido | przezwisko i nazwisko | — |
| apelidos | przezwisko i nazwisko | — |
| apelido3 | przezwisko i nazwisko | pusto |
| propina | łapówka i czesne | — |
| propinas | łapówka i czesne | — |
| fato | fakt i garnitur | — |
| fato3 | fakt i garnitur | pusto |
| ônibus | autobus drugiego wariantu, z rodzajnikiem | hasło „ônibus”, gdy językiem nauki jest portugalski europejski |
| trem | pociąg drugiego wariantu, z rodzajnikiem | hasło „trem”, gdy językiem nauki jest portugalski europejski |
| casa | dom i przypadek. „caso” dzieli jeden znak | — |

### polski i rosyjski

Rodzajnika nie ma przy żadnym ustawieniu. „pan” i „пан” to różne znaki, więc jeden nie odpowiada drugiemu. Dociąganie i cache: „woda”. Zapis „droga” z pary polski–hiszpański nie może tu wejść.

| Wpis | Musi być | Dalej niż jedna różnica |
|---|---|---|
| вода | woda | — |
| воде | woda. To forma słowa „вода” | — |
| воад | woda. Jedno przestawienie | — |
| вода3 | woda | pusto |
| pan | pan | patelnia. Angielskiego w tej parze nie ma. „пан” też nie, bo to inne znaki |
| пан | pan | patelnia i łacińskie „pan” |
| droga | droga | narkotyk |
| иду | iść | forma osobowa |
| idę | iść | rosyjskie słowo jako hasło, gdy językiem nauki jest polski |

### polski i chiński

Rodzajnika nie ma przy żadnym ustawieniu. Dociąganie i cache: „朋友”. Zapis „droga” z pary polski–hiszpański nie może tu wejść.

| Wpis | Musi być | Dalej niż jedna różnica |
|---|---|---|
| 朋友 | przyjaciel | — |
| 两个朋友 | przyjaciel. To sposób, w jaki chiński mówi o liczbie | — |
| 友朋 | przyjaciel. Dwa znaki zamienione miejscami | — |
| 朋友3 | przyjaciel | pusto |
| 去了 | iść albo jechać | opis aspektu zamiast tłumaczenia |
| droga | droga | narkotyk |
| herabta | herbata. Jedno przestawienie | — |

### hiszpański i angielski

Rodzajnik tylko wtedy, gdy językiem nauki jest hiszpański. Dociąganie i cache: „pie”. Polskie „pan” i polski pies do tej pary nie należą.

| Wpis | Musi być | Dalej niż jedna różnica |
|---|---|---|
| pan | chleb i patelnia | polskie „pan” |
| pie | stopa i ciasto | — |
| pies | stopa i ciasto. Jedna litera za dużo przy „pie” | polski pies |
| pie3 | stopa i ciasto | pusto |
| come | jeść i przyjść | — |
| actual | obecny i rzeczywisty | — |
| red | czerwony i sieć | — |
| cara | twarz i drogi | imię jako jedyny wynik; rodzaj żeński jako hasło przymiotnika |
