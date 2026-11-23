# Railway CLI — dostęp i diagnostyka

Instrukcja operacyjna, nie zapis aktualnego stanu produkcji. Bieżące priorytety określa [plan bety](../epics/E-001-google-play-beta/README.md), a zasady publikowania [CONTRIBUTING](../../CONTRIBUTING.md).

## Granice

- Railway wdraża backend z katalogu `backend`, nie aplikację Androida.
- Obecny deploy korzysta z [railway.toml](../../backend/railway.toml). Przygotowana [konfiguracja IaC](../../.railway/railway.ts) nie jest automatycznie stosowana; rzeczywisty deploy i regiony należy odczytać z konsoli/CLI.
- Region PostgreSQL jest konfigurowany osobno od backendu; po zmianie regionu sprawdź obie usługi i kopie wolumenu.
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

## Przejście na Railway IaC

Railway [wycofuje Config as Code 1 grudnia 2026](https://docs.railway.com/config-as-code). Przygotowany plik IaC opisuje tylko backend jako nazwany partial, zamiast zalecanego jednego pliku całego projektu, aby nie przejąć zarządzania PostgreSQL, wolumenem ani zmiennymi. Samo dodanie pliku do repozytorium nie zmienia konfiguracji Railway. Nie usuwaj jeszcze `backend/railway.toml`.

Przed przełączeniem, na właściwym projekcie i środowisku:

1. Sprawdź aktualną kopię bazy, brak cudzych zmian oczekujących w Railway oraz działający deploy i jego konfigurację. Użyj Node.js 22+, Railway CLI 5.75.0 lub nowszego i `npm ci`.
2. Po zatwierdzeniu pliku IaC w Git utwórz lokalny katalog `.local`, jeśli nie istnieje, i uruchom `railway config plan --out .local\railway-plan.json`. Plik planu jest lokalny i nie służy do publikacji. Nie używaj opcji odszyfrowywania ani wyświetlania wartości zmiennych.
3. Przejrzyj plan i jego surowy `changeSet`: tylko zamierzone zmiany backendu, bez usuwania usług, wolumenu i zmiennych; docelowo wyłącznie jedna replika EU West. CLI 5.75.0 może pokazać w tekście planu oba regiony jako usuwane, mimo że pole `after.multiRegionConfig` zawiera jedną replikę EU West. Test w osobnym projekcie potwierdził taki wynik zastosowania. Jednak [kod CLI](https://github.com/railwayapp/cli/blob/v5.75.0/src/iac/change_set.rs) normalizuje pojedynczy region z jedną repliką bez uwzględnienia jego nazwy: potwierdzono też, że zmiana między regionami może nie pojawić się w planie. Dlatego niezależnie porównuj obecne i docelowe regiony, nawet gdy plan nie pokazuje zmian, i weryfikuj regiony po wdrożeniu.
4. Dopiero po osobnej zgodzie zastosuj zweryfikowany, przypięty plan zgodnie z [instrukcją Railway](https://docs.railway.com/infrastructure-as-code). Potwierdź zapis ustawień Railway oraz stan usług. Jeżeli plan się zdezaktualizował, przygotuj i sprawdź nowy.
5. Dopiero po potwierdzeniu ustawień usuń stary TOML w osobnej zmianie i wdróż ją. Railway może wykrywać plik w katalogu backendu nawet bez jawnej ścieżki Config File. Po deployu sprawdź regiony, SHA, `/health/ready`, działanie bazy i kopie.

## Zmiany produkcji

Deploy, zmiana konfiguracji, skalowanie, migracja regionu lub zapis do bazy wymagają osobnego zlecenia. Przed nimi należy określić cel, kopię danych, kompatybilność starszych klientów, pomiar po zmianie i drogę wycofania.

Nie umieszczamy w publicznym repo lokalnych identyfikatorów dostępu, snapshotów zmiennych ani wyników zapytań do produkcji.
