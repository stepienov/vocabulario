# Odmiany i darmowe źródła — zestawienie z 27 XI 2026

*Dowód i kontekst dla [E-006](../README.md) z dnia dokumentu.*

- To nie jest aktualny opis produkcji ani backlog.
- Stan kodu: lokalne drzewo robocze z 27 XI 2026.
- Licencje i strony zewnętrzne sprawdzono 27 XI 2026.
- Liczby form pochodzą z jednorazowego pomiaru publicznych danych Kaikki dla pojedynczych popularnych słów. Nie pokazują, jaka część słownictwa użytkowników jest pokryta.

## 1. Jakich odmian brakuje

Legenda:
- ✅ jest i działa,
- ⚠️ jest, ale niepełne lub źle dopasowane do języka,
- ❌ **brakuje**, choć język ma odmianę,
- — język tego nie odmienia, więc nic nie brakuje.

| Język | Czasownik | Rzeczownik | Przymiotnik | Zaimek | Rodzajnik / określnik | Liczebnik |
|---|---|---|---|---|---|---|
| **polski** | ✅ | ❌ 7 przypadków × 2 liczby | ❌ rodzaj × przypadek × liczba + stopniowanie | ❌ ja/mnie/mi/mną | — | ❌ dwa/dwóch/dwoma |
| **rosyjski** | ⚠️ brak pary aspektowej i imiesłowów | ❌ 6 przypadków × 2 liczby | ❌ forma pełna i krótka + stopniowanie | ❌ он/его/ему | — | ❌ |
| **niemiecki** | ⚠️ brak Konjunktiv I | ❌ 4 przypadki × 2 liczby | ❌ odmiana mocna/słaba/mieszana + stopniowanie | ❌ er/ihn/ihm | ❌ der/die/das, ein, kein | — |
| **angielski** | ✅ | ❌ l. mnoga, w tym nieregularna (mouse→mice) | ❌ stopniowanie (good/better/best) | ❌ I/me/my/mine | — | — |
| **hiszpański** | ✅ | ❌ l. mnoga | ❌ rodzaj/liczba (bueno/buena/buenos) | ❌ zaimki nieakcentowane lo/le/se | ❌ el/la/los/las | — |
| **francuski** | ✅ | ❌ l. mnoga (cheval→chevaux) | ❌ beau/bel/belle/beaux | ❌ le/la/lui/leur | ❌ le/la/les, du/des | — |
| **włoski** | ⚠️ brak congiuntivo imperfetto | ❌ l. mnoga (uomo→uomini) | ❌ bello/bella/bei/begli | ❌ zaimki nieakcentowane | ❌ il/lo/la/gli | — |
| **portugalski BR** | ⚠️ brak infinitivo pessoal | ❌ l. mnoga | ❌ bom/boa/bons/boas | ❌ | ❌ o/a/os/as + ściągnięcia (do, na) | — |
| **portugalski PT** | ✅ | ❌ l. mnoga | ❌ bom/boa/bons/boas | ❌ | ❌ o/a/os/as + ściągnięcia | — |
| **arabski** | ⚠️ brak trybów (subjunctive/jussive) i strony biernej | ❌ 3 przypadki × l. poj./podwójna/mnoga (w tym mnoga łamana: كتاب→كتب) | ❌ zgoda + stopień wyższy (كبير→أكبر) | ❌ zaimki dołączane do wyrazu | ⚠️ ال tylko jako dopisek | — |
| **hindi** | ⚠️ brak aspektów i zgody z rodzajem | ❌ forma prosta/zależna/wołacz × 2 liczby (लड़का/लड़के/लड़कों) | ❌ odmiana na -ā (अच्छा/अच्छे/अच्छी) | ❌ मैं/मुझे/मेरा | — | — |
| **turecki** | ⚠️ tylko 4 czasy; brak trybów, przeczenia, -mış | ❌ 6 przypadków × przynależność × liczba (ev/evi/eve/evde/evim) | — | ❌ ben/beni/bana | — | — |
| **japoński** | ⚠️ siatka 6 osób zbędna, japoński nie odmienia przez osoby | — | ❌ **przymiotniki -i i -na się odmieniają** (高い/高くない/高かった) | — | — | — |
| **koreański** | ⚠️ zamiast poziomów grzeczności siatka 6 osób | — | ❌ **przymiotniki odmieniają się jak czasowniki** (예쁘다/예뻐요/예뻤어요) | — | — | — |
| **chiński** | ⚠️ płacisz za odmianę, której język nie ma (są tylko partykuły 了/着/过) | — | — | — | — | — |
| **wietnamski** | ⚠️ jak chiński | — | — | — | — | — |

Pozostałe części mowy (przysłówek, przyimek, spójnik, partykuła, wykrzyknik) prawie się nie odmieniają. Wyjątkiem jest stopniowanie przysłówków (szybko/szybciej, fast/faster), którego apka też nie ma.

**Sedno:** dla rzeczowników i przymiotników manifesty języków (`backend/app/lsp/<kod>/manifest.yaml`) już deklarują przypadki, liczby i rodzaje. Nic z tego jednak nie jest generowane, sprawdzane ani wyświetlane. Ta sekcja w kodzie leży martwa.

---

## 2. Darmowe źródła odmian

### 2.1. Jedno źródło dla wszystkich języków: Wiktionary → Kaikki

[Kaikki.org](https://kaikki.org/dictionary/) to gotowy, przetworzony zrzut angielskiej Wiktionary w JSON. Każda forma ma opis gramatyczny (tagi), np. `kota [genitive, singular]`.

**Pomiar z 27 XI 2026.** Pobrałem po jednym popularnym słowie na część mowy i policzyłem formy z tagami:

| Język | Czasownik | Rzeczownik | Przymiotnik | Inne |
|---|---|---|---|---|
| polski | czytać: 116 | kot: 20 | dobry: 39 | on: 32 |
| rosyjski | читать: 60 | дом: 30 | хороший: 36 | он: 103 |
| niemiecki | gehen: 105 | Haus: 28 | schön: 171 | der: 39 |
| angielski | go: 33 | mouse: 3 | good: 7 | he: 5 |
| hiszpański | comer: 204 | casa: 1 (l. mn.) | bueno: 12 | |
| francuski | manger: 62 | cheval: 2 | beau: 4 | |
| włoski | mangiare: 65 | uomo: 15 | bello: 9 | |
| portugalski | comer: 79 | casa: 2 | bom: 11 | |
| arabski | كتب: 143 | كتاب: 37 | كبير: 102 | |
| hindi | जाना: 258 | लड़का: 7 | अच्छा: 13 | |
| turecki | gelmek: 941 | ev: 100 | güzel: 51 | |
| japoński | 食べる: 207 | — | 高い: 59, 静か: 73 | |
| koreański | 먹다: 48 | — | 예쁘다: 77 | |
| chiński / wietnamski | 吃: 1 / ăn: 3 | — | — | brak odmiany, zgodnie z oczekiwaniem |

Formy są oznaczone tak, że da się je przypisać do kluczy apki. Przykłady: koreańskie mają oznaczenia `formal/informal/polite` × czas, tureckie `przypadek × posiadacz × liczba`, arabskie `przypadek × liczba × określoność`.

**Jak się do tego dostać:**
- **Plik per słowo:** np. `https://kaikki.org/dictionary/Polish/meaning/k/ko/kot.jsonl`. Działa, ale to nie jest oficjalne API: nie ma gwarancji dostępności ani limitów zapytań.
- **Cały język w jednym pliku JSONL** do pobrania i trzymania we własnej bazie, czyli własne „API” bez limitów. Pliki są duże, np. polski ma ok. 856 MB. Ostatnia ekstrakcja: 30 X 2026 z zrzutu Wiktionary z 1 X 2026.
- **Oficjalne API Wiktionary (MediaWiki)** zwraca kod strony, a nie gotowe tabele. Tabele odmian powstają z szablonów i trzeba je samemu przetworzyć. Właśnie to robi Kaikki.

**Licencja:** CC BY-SA. Użycie komercyjne w płatnej apce jest dozwolone, pod dwoma warunkami:
1. Trzeba podać źródło, np. na ekranie „Źródła” w apce.
2. Udostępniane dalej dane pochodne (tabele odmian) muszą zostać na tej samej licencji. Kod apki nie musi być otwarty.

Sposób łączenia tych danych z treścią z AI na jednej karcie warto skonsultować z prawnikiem.

**Ograniczenia, które wyszły w pomiarze:**
- **Czasy złożone nie zawsze są w danych.** Hiszpański i włoski mają 0 form wielowyrazowych, więc np. *he comido* czy *ho mangiato* trzeba złożyć samemu: posiłkowy + imiesłów. Imiesłów jest w danych, a włoski i niemiecki podają też czasownik posiłkowy. Francuski i niemiecki mają czasy złożone gotowe. Angielski ma tylko 5 form podstawowych (go/goes/going/went/gone), resztę składa się regułą.
- **Portugalski to jedna pula**, bez rozdziału na BR i PT.
- **Rzadkie słowa, slang i wyrażenia wielowyrazowe** mogą nie mieć tabel. Pokrycia całego słownictwa apki nie mierzyłem, bo sprawdziłem tylko popularne słowa.
- **Jakość jest społecznościowa.** Dla popularnych słów jest dobra, ale bez gwarancji.

### 2.2. Narzędzia dla konkretnych języków

Większość z nich to biblioteki lub dane do zainstalowania na własnym serwerze, a nie zewnętrzne API.

| Język | Narzędzie | Co daje | Licencja | Pewność ustaleń |
|---|---|---|---|---|
| polski | **Morfeusz 2 + słownik SGJP** | pełna odmiana wszystkich części mowy, ok. 330 tys. leksemów | BSD-2 (program i dane) | licencja potwierdzona w wyszukiwaniu i publikacji ACL; strona projektu nie odpowiadała |
| polski | UniMorph `pol` (z SGJP) | rzeczownik, czasownik, przymiotnik; 13,9 mln form | CC BY-SA 3.0 | ✔ sprawdzone |
| rosyjski | **pymorphy3** + słownik OpenCorpora | odmiana i generowanie form wszystkich części mowy | kod MIT, słownik CC BY-SA | ✔ sprawdzone |
| rosyjski, arabski, turecki | UniMorph | rzeczownik, czasownik, przymiotnik | CC BY-SA 3.0 | ✔ sprawdzone |
| niemiecki | german-nouns (z Wiktionary) | ok. 100 tys. rzeczowników: rodzaj, przypadki, liczba | CC BY-SA 4.0 | z wyszukiwania |
| niemiecki, hiszpański, francuski, włoski, angielski, hindi | UniMorph | tylko czasowniki (niemiecki też rzeczowniki) | CC BY-SA 3.0 | ✔ sprawdzone |
| angielski | **LemmInflect** | l. mnoga, stopniowanie, formy czasownika | MIT | ✔ sprawdzone |
| hiszpański, francuski, włoski, portugalski | **mlconjug3** | koniugacja; nieznane czasowniki zgaduje modelem ML | MIT | ✔ sprawdzone |
| hiszpański, francuski, włoski, portugalski | **verbecc** | pełna koniugacja | LGPL-3.0 (w porządku jako biblioteka) | ✔ sprawdzone |
| portugalski | **MorphoBr** | rzeczownik, przymiotnik, czasownik, przysłówek; 10,9 mln form | Apache 2.0 | ✔ sprawdzone |
| arabski | Qutrub | koniugacja czasowników z trybami i stroną bierną | GPL; na samym serwerze zwykle OK, bo nie jest rozpowszechniany | ✔ sprawdzone |
| turecki | **Zemberek** | morfologia tureckiego | Apache 2.0 | licencja ✔; generowania form nie testowałem |
| japoński | **JMdict** + tabele koniugacji JMdictDB (np. projekt jconj) | klasa słowa (v1, v5k, adj-i, adj-na), a z niej koniugacja regułami | JMdict CC BY-SA 4.0 z dodatkowymi warunkami EDRDG; licencji jconj nie sprawdziłem | częściowo |
| koreański | Kaikki (patrz 2.1) | pełne tabele czasowników i przymiotników z poziomami grzeczności | CC BY-SA | ✔ pomiar |
| hindi | tylko Kaikki | czasownik: 258 form, rzeczownik, przymiotnik | CC BY-SA | ✔ pomiar |
| wszystkie | Wikidata Lexemes | prawdziwe API (SPARQL), formy z cechami | **CC0**, bez warunków | pokrycie nierówne i niezmierzone |

Japoński i koreański odmieniają się bardzo regularnie. Gdy zna się klasę słowa (z JMdict lub Kaikki), formy można policzyć w kodzie, bez AI i bez wielkiej bazy.

### 2.3. Licencje w praktyce

- **MIT, Apache, BSD, CC0:** niskie ryzyko, ale nie zerowe. MIT, BSD i Apache wymagają zachowania informacji o prawach autorskich i tekstu licencji w dystrybucji (Apache także pliku NOTICE, jeśli istnieje). Apache 2.0 zawiera też postanowienia patentowe. CC0 nie ma tych obowiązków. Sposób atrybucji w apce opisuje [E-006/F-010](../features/F-010-atrybucja-zrodel/README.md).
- **CC BY-SA (Wiktionary, UniMorph, OpenCorpora, JMdict):** wolno używać komercyjnie, ale trzeba podać źródło w apce, a dane pochodne udostępniać na tej samej licencji. Do konsultacji z prawnikiem: czy karta łącząca te dane z treścią AI to „utwór pochodny” i czy płatny dostęp nie koliduje z zakazem dodatkowych ograniczeń.
- **GPL (Qutrub):** biblioteka działająca tylko na serwerze, bez rozpowszechniania, zwykle nie wymaga otwierania kodu. Wersja AGPL by tego wymagała; Qutrub nie jest na AGPL.

---

## Ograniczenia ustaleń

- Pomiar objął po jednym popularnym słowie na język i część mowy. Pokrycie całego słownictwa użytkowników jest nieznane.
- Nie sprawdzono licencji `jconj` ani `korean_conjugation`.
- Nie sprawdzono, czy Zemberek generuje formy.
- Licencję Morfeusza 2 potwierdzają tylko wyniki wyszukiwania i publikacja ACL. Strona projektu nie odpowiadała.
- Ocena prawna CC BY-SA dla płatnej aplikacji z mieszaną treścią wymaga konsultacji ([E-006/F-010](../features/F-010-atrybucja-zrodel/README.md)).

## Źródła (sprawdzone 27 XI 2026)

- Kaikki: https://kaikki.org/dictionary/ i przykład https://kaikki.org/dictionary/Polish/meaning/k/ko/kot.html
- Wiktextract (format danych): https://github.com/tatuylonen/wiktextract
- CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/
- UniMorph: https://unimorph.github.io/
- Morfeusz 2, licencja: https://morfeusz.sgjp.pl/doc/license/en (tylko z wyszukiwania) i https://aclanthology.org/L14-1597/
- pymorphy3: https://pypi.org/project/pymorphy3/; słowniki: https://pypi.org/project/pymorphy3-dicts-ru/
- Zemberek: https://github.com/ahmetaa/zemberek-nlp
- LemmInflect: https://github.com/bjascob/LemmInflect
- mlconjug3: https://github.com/Ars-Linguistica/mlconjug3
- verbecc: https://github.com/bretttolbert/verbecc
- Qutrub: https://github.com/linuxscout/qutrub
- MorphoBr: https://github.com/LR-POR/MorphoBr
- german-nouns: https://github.com/gambolputty/german-nouns
- JMdict / EDRDG: https://www.edrdg.org/edrdg/licence.html; jconj: https://github.com/yamagoya/jconj
- Wikidata Lexemes: https://www.wikidata.org/wiki/Wikidata:Lexicographical_data
