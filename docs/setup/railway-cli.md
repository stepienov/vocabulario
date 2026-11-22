# Railway CLI — dostęp i diagnostyka

Instrukcja operacyjna, nie zapis aktualnego stanu produkcji. Bieżące priorytety określa [plan bety](../epics/E-001-google-play-beta/README.md), a zasady publikowania [CONTRIBUTING](../../CONTRIBUTING.md).

## Granice

- Railway wdraża backend z katalogu `backend`, nie aplikację Androida.
- Konfiguracja oczekiwana jest w [railway.toml](../../backend/railway.toml); rzeczywisty deploy i regiony należy odczytać z konsoli/CLI.
- Status i ograniczony odczyt logów nie oznaczają zgody na deploy, zmiany zmiennych, regionów ani zapis do bazy.
- Nie uruchamiaj `railway variables` w logowanym terminalu ani nie wklejaj surowego eksportu zmiennych do raportu — może zawierać sekrety.
- Stare pomiary infrastruktury są w [archiwum optymalizacji](../epics/E-002-szybka-nauka/sources/optymalizacja-requestow.md), nie należy traktować ich jako aktualnej konfiguracji.

## Instalacja

Jeśli CLI nie jest jeszcze zainstalowane, jedną z opcji na Windows jest npm:

```powershell
npm install -g @railway/cli
railway --version
```

W środowiskach z kontrolą aplikacji WDAC sam plik `railway.exe` może być blokowany. Sprawdź, który program uruchamia `Get-Command railway`; nie obchodź polityki komputera.

## Uwierzytelnienie

Sekrety pozostają w lokalnym `.env` lub zatwierdzonym magazynie sekretów, nigdy w dokumentacji. [Szablon konfiguracji](../../.env.example) zawiera wyłącznie nazwy i przykładowe wartości.

| Zmienna | Rodzaj dostępu |
|---|---|
| `RAILWAY_TOKEN` | Token projektu; preferowany, gdy wystarczy dostęp do jednego projektu |
| `RAILWAY_API_TOKEN` | Token konta/workspace; szerszy zakres, tylko jeśli wymagany |
| `RAILWAY_PROJECT_ID`, `RAILWAY_SERVICE_ID`, `RAILWAY_ENVIRONMENT` | Wybór celu operacji |

Token projektu i token konta nie są zamienne. `PROD_DATABASE_URL`, jeśli skonfigurowany lokalnie, jest oddzielnym dostępem do bazy i nie zastępuje CLI. Nie zakładaj, że każdy współpracownik ma te wartości.

Interaktywne logowanie, jeśli wybrano ten sposób:

```powershell
railway login
railway link
```

Przed zatwierdzeniem linkowania sprawdź projekt, środowisko i serwis.

## Odczyt stanu

Z katalogu repozytorium i po sprawdzeniu celu:

```powershell
railway status
railway service status
railway deployment list
railway logs -n 50
```

Składnia zależy od wersji CLI; w razie różnic użyj pomocy danej komendy. Logi mogą zawierać dane użytkowników — czytaj tylko potrzebny zakres, redaguj dane przed publikacją.

Publiczny smoke:

```powershell
Invoke-RestMethod https://vocabulario.up.railway.app/health
```

`/health` nie potwierdza pełnego działania usługi ani SHA wdrożonego kodu. Weryfikacja wdrożenia wymaga zestawienia commita z udanym deploymentem oraz oddzielnych testów funkcjonalnych.

## Zmiany produkcji

Deploy, zmiana konfiguracji, skalowanie, migracja regionu lub zapis do bazy wymagają osobnego zlecenia. Przed nimi należy określić cel, kopię danych, kompatybilność starszych klientów, pomiar po zmianie i drogę wycofania.

Nie umieszczamy w publicznym repo lokalnych identyfikatorów dostępu, snapshotów zmiennych ani wyników zapytań do produkcji.
