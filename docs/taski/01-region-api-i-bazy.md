# Task 01. Jedna replika API przy bazie

Dokument źródłowy: `docs/optymalizacja-requestow.md`, rozdział 0, „Odległość procesu API od bazy”.

## Zakres

Serwis API `vocabulario` ma jedną replikę, w tym samym regionie co Postgres, i łączy się z bazą po prywatnej sieci Railway. Bez zmiany kodu aplikacji.

Podział pracy: wykonawca sprawdza stan tylko do odczytu, przygotowuje zmianę w `backend/railway.toml` i dokumentacji, przekazuje ją użytkownikowi i po wdrożeniu mierzy efekt. Zmianę w Railway (deploy z `main` albo panel) robi użytkownik.

Poza zakresem: przeniesienie bazy do Europy. To dałoby telefonowi krótszą drogę do API, ale wymaga migracji wolumenu Postgresa i przerwy. Można to rozważyć po tasku 11, gdy żądania będą robić po 1–3 podróże do bazy.

## Zależności

Brak. Może iść równolegle z taskiem 00.

## Warunek startu

- `railway status` działa (shim npm, token z `.env`, `docs/railway-cli.md`). Gdy nie działa, przerwij i napisz, co zwróciło. Bez CLI region bazy trzeba odczytać w panelu, co robi użytkownik.
- `GET https://vocabulario.up.railway.app/health` daje `status=ok`.

## Stan 8 listopada 2026

- `multiRegionConfig` serwisu: `europe-west4-drams3a` × 1 i `us-west2` × 1. Ustawione w panelu Railway, nie w `backend/railway.toml`.
- Postgres stoi w USA (`sfo` w danych instancji).
- Telefon trafia do repliki europejskiej (instancja `ef650127`, krawędź `europe-west4`).
- Podróż replika europejska → baza około 141 ms, replika amerykańska → baza kilka ms.
- Proces: jeden worker uvicorn (`backend/Dockerfile`), pula SQLAlchemy domyślna (`backend/app/db/session.py`: 5 połączeń i 10 nadmiarowych).

## Pliki

- `backend/railway.toml`: `multiRegionConfig` w `[deploy]`. Konfiguracja jako kod, żeby region był w historii repo i wracał przy każdym deployu.
- `docs/railway-cli.md`: region API, region bazy, liczba replik.
- Bez zmian w `backend/app`.

## Zachowanie po zmianie

- Wszystkie żądania telefonu obsługuje jedna instancja w regionie bazy.
- Droga telefon → krawędź Railway w Europie → replika w USA wydłuża każde żądanie HTTP o około 140–160 ms w jedną stronę. Każde żądanie robi dziś od kilku do kilkunastu podróży do bazy po około 141 ms, więc bilans jest wyraźnie dodatni.
- `_inflight`, `_claimed`, `_enrich_semaphore()`, `resume_pending_enrichment`, watchdog i `resume_unfinished_jobs` działają w jednym procesie. Ta sama karta nie jest już wzbogacana w dwóch procesach naraz.

## Kroki

Wykonawca:

1. Odczytaj region usługi Postgres: `railway status --json` (pole regionu instancji usługi Postgres). Zapisz dokładny identyfikator regionu Railway (postaci `us-west2`). Gdy JSON nie pokazuje regionu bazy, przerwij i poproś użytkownika o odczyt z panelu (Postgres → Settings → Region).
2. Sprawdź, że `DATABASE_URL` serwisu API wskazuje host prywatny (`*.railway.internal`), nie publiczny proxy. `railway variables --service vocabulario --json`, a z wartości wypisz wyłącznie host, bez reszty adresu. Host publiczny: zapisz to w raporcie jako krok dla użytkownika (przełączenie zmiennej na referencję prywatną `${{Postgres.DATABASE_URL}}`). Sam niczego nie zmieniaj.
3. Zmierz stan „przed” zapytaniami z sekcji „Sprawdzenie”, grupa „Po wdrożeniu” (odczyt produkcji). Zapisz liczby w raporcie.
4. Dopisz do `[deploy]` w `backend/railway.toml` region `us-west2` i `numReplicas = 1`. Nie wpisywać `sfo`. Odczyt z 8 listopada 2026: działający Postgres jest w starszym `sfo`, ale Railway przyjmuje tylko `us-west2`, `us-east4-eqdc4a`, `europe-west4-drams3a` i `asia-southeast1-eqsg3a`. `sfo` blokuje deploy. Replika API w `us-west2` jest o kilka milisekund od tej bazy. Redeployu Postgresa nie robić: przeniósłby wolumen i zatrzymał bazę.
5. Dopisz do `docs/railway-cli.md` region API, region bazy i liczbę replik.
6. Raport i stop.

Użytkownik:

7. Wdrożenie zmiany z `railway.toml` (wejście na `main`) albo to samo ustawienie w panelu: Service → Settings → Deploy → Regions. Ustawienie w panelu i w pliku musi być to samo, bo plik nadpisuje panel przy deployu.
8. Gdy krok 2 wykazał host publiczny: zmiana `DATABASE_URL` na referencję prywatną.

Wykonawca, na prośbę użytkownika po wdrożeniu:

9. Pomiar „po” i porównanie z krokiem 3.

## Sprawdzenie

Lokalnie, wykonawca:

- `backend/railway.toml` ma jedno `multiRegionConfig` z `us-west2` i `numReplicas = 1`, reszta pliku bez zmian. Nie ma w nim `sfo`,
- `docs/railway-cli.md` ma region API, region bazy i liczbę replik,
- raport zawiera host `DATABASE_URL` (prywatny albo publiczny) bez hasła i pomiar „przed”.

Po wdrożeniu (odczyt produkcji, konto `nowy4@test.com`, profil polski → hiszpański):

- `railway status`: jedna aktywna instancja, w regionie bazy,
- log HTTP Railway z 15 minut ruchu telefonu: jedno `deploymentInstanceId` przy wszystkich żądaniach,
- po dowolnym wywołaniu modelu przerwa między `llm_usage.created_at` a `llm_call_payloads.created_at` tego samego wywołania poniżej 50 ms (dziś 430–575 ms):

  ```sql
  select u.purpose, extract(milliseconds from p.created_at - u.created_at) as gap_ms
  from llm_usage u join llm_call_payloads p on p.llm_usage_id = u.id
  where u.created_at > now() - interval '30 minutes'
  order by u.created_at desc limit 20;
  ```

- szukanie `prado` (gotowy zapis): `duration_ms` w `app_logs` poniżej 1 s (dziś 3,0–3,5 s), na krawędzi poniżej 1,5 s. Kod się nie zmienił, więc to efekt samej odległości:

  ```sql
  select created_at, duration_ms from app_logs
  where event = 'http_request' and http_path = '/api/v1/lookup/cached'
    and created_at > now() - interval '30 minutes'
  order by created_at desc limit 20;
  ```

- `GET /cards/{id}`: na krawędzi poniżej 600 ms (dziś 1,7–2,9 s),
- `GET /sync/pull`: p50 z godziny ruchu poniżej 1 s (dziś około 3,2 s),
- typowa karta od wiersza do `ready`: 25–30 s (dziś 43 s).

## Ryzyka i wycofanie

- Każde żądanie telefonu z Europy dostaje stały koszt drogi przez Atlantyk. Dla żądań z jedną podróżą do bazy (po taskach 04–06) to większość czasu. Cel z punktu 1 (krawędź poniżej 600 ms) już to uwzględnia.
- Jedna replika to brak zapasu przy awarii instancji. `restartPolicyType = ON_FAILURE` i healthcheck zostają.
- Wycofanie (użytkownik): usunąć `multiRegionConfig` z `railway.toml` i przywrócić w panelu `europe-west4-drams3a` × 1 i `us-west2` × 1, potem redeploy.
