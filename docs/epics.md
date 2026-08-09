# Epics — Vocabulario

Dokument długoterminowych epików (poza bieżącą kolejką sprintową).
Bieżące / gotowe do implementacji feature’y: [`plan-2026-08-04.md`](./plan-2026-08-04.md).

**Statusy:** `parked` = nie robimy teraz · `ready` = do rozbicia na feature’y · `in progress` · `done`

---

## Status epików

| ID | Epic | Horyzont | Status |
|----|------|----------|--------|
| E-01 | Shared / starter content (paczki słów) | późniejsze release’y | parked |

---

## E-01 — Shared / starter content (paczki słów)

**Status:** `parked` — **olewamy w bieżącej pracy.** Do decyzji i rozbicia dopiero przy późniejszych release’ach.

**Kontekst:** Anki wygrywa gotowymi deckami. U nas `PacksScreen` to placeholder (orphan route); stringi wspominają „CEFR × kategorie”, ale **nie ma schematu packów** — tylko model list + kart. Osobny katalog „language packs” w kodzie dotyczy typologii L2 (czasy / koniugacja), nie treści słownikowej.

### Cele (po co w ogóle)

- Skrócić czas od onboardingu do pierwszej wartości: user nie startuje z pustą apką.
- Dać sensowny starter pod **parę językową + poziom CEFR** (i ewentualnie temat).
- Konkurować z Anki na „mam co robić od razu”, bez kopiowania marketplace’u community decków.
- Docelowo: treść wysokiej jakości w **Waszym** formacie karty (gloss, POS, przykłady, distractory) — nie dump Anki.

### Kierunki rozważane (nie zdecydowane)

| Wariant | Idea | Plus | Minus |
|---------|------|------|-------|
| A. Kuratorowane paczki | Katalog L2 × CEFR × temat → instalacja jako `WordList` | jakość, powtarzalność, shared `LexicalEntry` | CMS/katalog, seed, utrzymanie, „schema packów” |
| B. Generuj N słów (AI) | Modal: CEFR + suwak 1–50 → nowa lista, kafelki `pending` | szybki MVP, personalizacja (exclude posiadanych lemma) | koszt LLM, jakość, exact-N, brak „Anki-like” katalogu |
| C. Hybrid | Mały curated core + generate jako uzupełnienie | balans | złożoność dwóch systemów |

**Na ten moment żaden wariant nie jest wybrany.** E-01 istnieje po to, żeby nie zgubić tematu i świadomie nie wrzucać go do sprintu.

### Dlaczego problematyczne (do ustalenia później)

1. **Model produktu** — instalacja musi spiąć się z listami („Uczę się” vs biblioteka). Wrzucenie 100+ słów prosto w SRS psuje kolejkę; sama lista bez CTA też może zostać martwa.
2. **Jakość vs Anki** — gotowe decki Anki są „wystarczająco dobre” mimo szumu; generatywne paczki bez twardej walidacji będą gorsze; curated wymaga pracy redakcyjnej.
3. **Koszt** — każdy lemma bez wspólnego `LexicalEntry` = enrichment LLM (jak ręczne dodanie × N). Shared cache pomaga dopiero przy curated / preseed.
4. **Brak infrastruktury** — nie ma tabel packów, API katalogu, ani pipeline’u publikacji; `PacksScreen` kłamie „schema ready”.
5. **Offline** — install/katalog wymaga netu; spięcie z full offline (#1 w planie) dopiero po domknięciu mirroru list.
6. **Scope creep** — łatwo ześlizgnąć się w marketplace, wersjonowanie decków, community upload — tego nie chcemy na starcie.
7. **Duplikaty i exclude** — user już ma słowa; generowanie musi omijać posiadane lemma (token limits przy dużym decku).

### Założenia, gdy wrócimy do tematu

- Org słów bez zmian: **listy + karty**; paczka / batch **materializuje się jako lista użytkownika**, nie osobny byt w SRS.
- Nie budować community marketplace w pierwszym podejściu.
- Najpierw decyzja produktowa: **A vs B vs hybrid**, potem dopiero design API i UI.
- Gate jakości: nie publikować curated / nie odpalać generate na prod bez smoke’u formatu karty (gloss, distractory, CEFR).
- Placeholder `PacksScreen` / route `PACKS` — albo podpiąć pod wybrany wariant, albo usunąć przy porządkach UI; nie rozwijać „w ciemno”.

### Out of scope (jawnie)

- Implementacja w release’ach powiązanych z planem `2026-08-04` (w tym full offline).
- Wybór finalnego UX w tym dokumencie.
- Seed konkretnych języków / list lemma.

### Definition of ready (żeby odparkować E-01)

- [ ] Wybrany wariant (A / B / hybrid) + uzasadnienie.
- [ ] Opisane AC dla pierwszego slice’a (np. 1 język, 1 CEFR, albo sam generate modal).
- [ ] Decyzja: koszt AI / preseed `LexicalEntry`.
- [ ] Feature rozbity w planie sprintowym (osobny plik lub sekcja w `plan-*.md`).

---

## Jak dodawać kolejne epiki

Format jak wyżej: ID, status, cele, warianty/otwarte decyzje, ryzyka, założenia, DoR.  
Parked epiki nie trafiają do checklist implementacyjnych bez przejścia DoR.
