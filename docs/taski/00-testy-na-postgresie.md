# Task 00. Testy na lokalnym Postgresie

## Po co

Dzisiejsze testy backendu (`backend/tests/`, 475 zielonych i 2 pominięte 8 listopada 2026) nie łączą się z bazą. Logikę sprawdzają na atrapach i czystych funkcjach. Taski 02–11 zmieniają zachowanie, którego atrapa nie pokaże:

- `INSERT … ON CONFLICT DO NOTHING` i `SELECT … FOR UPDATE` przy równoczesnych żądaniach (04, 05, 06, 08),
- `SAVEPOINT` w jednej transakcji (11),
- `updated_at` przy jawnym `updated_at=LearningCard.updated_at` w `update()` (03),
- liczba zapytań SQL na ścieżce żądania i wypożyczone połączenia puli (04, 05, 06),
- zapytania wyboru kart do wznowienia i kolejki importu (03, 11).

Ten task dodaje marker `pg` i fixture, które uruchamiają takie testy na lokalnej bazie testowej. Bez bazy testy `pg` są pomijane, więc CI (`.github/workflows/ci.yml`, bez Postgresa) działa jak dziś.

## Zależności

Brak. Task idzie przed 02, bo od 02 każdy task ma testy `[pg]`.

## Warunek startu

Lokalny Postgres odpowiada i ma pustą bazę testową, której nazwa kończy się na `_test`. Dziś `DATABASE_URL` z `.env` wskazuje `127.0.0.1:54780/vocabulario` i ten port nie odpowiadał 8 listopada. Docker nie jest zainstalowany.

Wykonawca sprawdza połączenie z adresem z `TEST_DATABASE_URL` (`.env`). Gdy zmiennej nie ma albo baza nie odpowiada, przerywa i prosi użytkownika o uruchomienie Postgresa i założenie bazy, na przykład:

```sql
CREATE DATABASE vocabulario_test OWNER vocabulario;
```

oraz o wpis w `.env`: `TEST_DATABASE_URL=postgresql+asyncpg://vocabulario:…@127.0.0.1:<port>/vocabulario_test`. Wykonawca nie zakłada bazy sam i nie używa `DATABASE_URL` ani `PROD_DATABASE_URL`.

## Pliki

- `backend/tests/conftest.py` (nowy),
- `backend/tests/pg_factories.py` (nowy),
- `backend/tests/test_pg_harness.py` (nowy),
- `backend/pyproject.toml`: marker `pg`,
- `.env.example`: pusty wpis `TEST_DATABASE_URL=` z komentarzem.

## Zachowanie

`conftest.py`, na samej górze, przed jakimkolwiek importem z `app`:

- czyta `TEST_DATABASE_URL` ze środowiska albo z `.env` w katalogu głównym repo,
- gdy adres jest ustawiony: host musi być `localhost`, `127.0.0.1` albo `::1`, a nazwa bazy kończyć się na `_test`. Inaczej `pytest.exit` z komunikatem. To chroni przed czyszczeniem bazy deweloperskiej i produkcji,
- ustawia `os.environ["DATABASE_URL"] = TEST_DATABASE_URL`. `app.db.session.engine` powstaje przy imporcie z `get_settings()`, a zmienna środowiska ma pierwszeństwo przed plikiem `.env` (`app/core/config.py`, `env_file`). Testy bez markera bazy nie dotykają, więc dla nich zmiana nic nie znaczy,
- `pytest_collection_modifyitems`: testy z `pg` dostają `skip`, gdy adresu nie ma albo pierwsze połączenie się nie udało.

Fixture `pg` (zakres funkcji, `async`):

- raz na sesję testów `apply_schema(engine, Base.metadata)` z `app/db/migrations.py`, czyli to samo, co robi `lifespan`,
- przed każdym testem `TRUNCATE` wszystkich tabel z `Base.metadata.sorted_tables` z `RESTART IDENTITY CASCADE`,
- zwraca `async_session_factory`,
- po teście: `drain_background` z taska 02, gdy już istnieje (`hasattr`), czyszczenie `_claimed` i `_inflight` z `card_jobs`, `lookup_jobs`, `lookup_category_jobs`, potem `await engine.dispose()`. Pętla zdarzeń jest osobna na każdy test (`asyncio_default_fixture_loop_scope = "function"`), a połączenia asyncpg z poprzedniej pętli nie działają w następnej.

Fixture `pg_client`: `httpx.AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")` bez uruchamiania `lifespan` (schemat jest z fixture `pg`, a wznowienia i watchdog nie mają startować w testach).

`pg_factories.py`: `create_user`, `create_profile(user, app_lang, learning_lang)`, `create_list(profile, name)`, `create_card(profile, lemma, pos, *, status, content, deck_id)`, `auth_headers(user)` przez `create_access_token` z `app/core/security.py`. Pola modeli według `backend/app/models/__init__.py`. Karta na liście systemowej dostaje `SrsState` tak jak w `create_card` endpointu.

Marker w `pyproject.toml`:

```toml
markers = [
    "visual: HTML/PNG import galleries (needs Playwright; not run in CI)",
    "pg: needs local Postgres from TEST_DATABASE_URL (skipped without it)",
]
```

`addopts` zostaje `-m 'not visual'`, więc `pg` biegnie razem z resztą, gdy baza jest.

## Kroki

1. Marker i `conftest.py` z ochroną adresu.
2. Fixture `pg` i `pg_client`.
3. `pg_factories.py`.
4. `test_pg_harness.py`.

## Sprawdzenie

Lokalnie, wykonawca:

- bez `TEST_DATABASE_URL`: `.venv\Scripts\python.exe -m pytest -q` daje te same liczby co przed taskiem plus pominięte testy `pg`,
- z `TEST_DATABASE_URL`: `test_pg_harness.py` przechodzi:
  - wstawiona karta jest widoczna w tym samym teście i nie ma jej w następnym (`TRUNCATE` działa),
  - `GET /api/v1/me` przez `pg_client` z `auth_headers` daje 200,
  - dwa równoczesne `INSERT … ON CONFLICT DO NOTHING` do `lookup_query_cache` z tym samym kluczem dają jeden wiersz,
- `TEST_DATABASE_URL` z hostem innym niż lokalny albo bazą bez `_test`: pytest kończy się od razu komunikatem, zanim cokolwiek się połączy,
- `python scripts/ci_check.py` zielone.

## Ryzyka

- Import `app` w module testu przed `conftest.py` nie jest możliwy (pytest ładuje `conftest.py` pierwszy), ale import w pluginie albo w `sitecustomize` ominąłby podmianę adresu. Takich dziś nie ma.
- `TRUNCATE … CASCADE` na każdym teście kosztuje dziesiątki milisekund przy kilkudziesięciu tabelach. Testów `pg` będzie kilkadziesiąt, więc to kilka sekund.
