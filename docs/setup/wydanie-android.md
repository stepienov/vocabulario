# Wydanie Androida (AAB do Google Play)

Krótka instrukcja operatora. Nie zawiera kluczy ani haseł; klucz uploadu jest poza repozytorium.

## Parametry release

Build release **nie wystartuje**, dopóki nie podasz wszystkich poniższych wartości (debug i CI ich nie potrzebują):

| Parametr | Znaczenie |
|---|---|
| `-Prelease.application.id` | Ostateczny pakiet aplikacji: **`io.vocabulario.app`** (decyzja z 2026-11-20, po pierwszym uploadzie do Play nie do zmiany). To osobna aplikacja od dotychczasowego debug `com.vocabulario.app`. |
| `-Prelease.version.code` | Liczba całkowita ≥ 1, każdy upload do Play wyższy niż poprzedni. |
| `-Prelease.version.name` | Nazwa widoczna dla użytkownika, np. `0.2.0`. |
| `-Papi.base.url` | `https://<domena>/api/v1`. Tylko https, bez portu, hosta lokalnego, adresu IP, danych logowania i query. Sprawdzane przy buildzie i w aplikacji. |

Podpis (klucz uploadu) z `UPLOAD_KEYSTORE_FILE`, `UPLOAD_KEYSTORE_PASSWORD`, `UPLOAD_KEY_ALIAS`, `UPLOAD_KEY_PASSWORD` (zmienne środowiskowe albo `-Prelease.keystore.file`, `-Prelease.keystore.password`, `-Prelease.key.alias`, `-Prelease.key.password`). Release bez klucza nie zostanie zbudowany; nigdy nie jest podpisywany kluczem debug. Klucz trzymaj poza Git (`*.jks` jest ignorowane), a w Play włącz Play App Signing.

```powershell
cd android
# W PowerShell każdy parametr -P w cudzysłowie.
.\gradlew.bat :app:lintRelease :app:bundleRelease --console=plain `
  "-Prelease.application.id=<pakiet>" "-Prelease.version.code=<n>" `
  "-Prelease.version.name=<x.y.z>" "-Papi.base.url=https://<domena>/api/v1"
python ..\scripts\check_aab_16kb.py app\build\outputs\bundle\release\app-release.aab
```

Wynik: `android\app\build\outputs\bundle\release\app-release.aab`. Skrypt sprawdza, czy biblioteki 64-bit są gotowe na strony 16 KB (kod 0 = OK).

## Co robi build release

- Ruch tylko HTTPS (`usesCleartextTraffic=false`); debug nadal dopuszcza lokalny HTTP.
- Bez kopii zapasowej i transferu danych (sesja, baza i kolejki są związane z kontem i urządzeniem).
- Schemat bazy Room jest eksportowany do `android\app\schemas\` (podstawa pod testy migracji; same testy wymagają urządzenia).
- Minifikacja R8 jest wyłączona do czasu testu na urządzeniu; decyzja o jej włączeniu należy do właściciela po próbie na S24.

## Przejście z buildu debug do Play

Nowy pakiet to osobna instalacja: nie zastąpi debug `com.vocabulario.app` i nie przeniesie jego danych lokalnych. Praca z kolejek debug musi być wysłana (synchronizacja) przed zainstalowaniem wersji z Play; potem logowanie na to samo konto pobiera dane z serwera. Do tego czasu nie odinstalowuj debug.

## Wymuszenie aktualizacji (HTTP 426)

Aplikacja wysyła `X-App-Version-Code`. Gdy serwer ma `MIN_APP_VERSION_CODE` > 0, a żądanie `/api/v1/...` ma niższą (albo brakującą) wersję, odpowiada **426 `app_update_required`**. Aplikacja pokazuje ekran aktualizacji z przyciskiem do własnego wpisu w Play; sesja, biblioteka i kolejki zostają, nic nie jest kasowane ani wylogowywane. Poza bramką zostają: dokumenty prawne, usuwanie konta, potwierdzenia z e-maili, wylogowanie, zdarzenia poczty i `/admin/`.

Kolejność podniesienia minimum:

1. Opublikuj i sprawdź nowy build (wyższy `versionCode`) na właściwym tracku.
2. Ustaw w Railway `ANDROID_PACKAGE` (pakiet release), `APP_UPDATE_URL=https://play.google.com/store/apps/details?id=<pakiet>` i `MIN_APP_VERSION_CODE=<versionCode nowego buildu>`. Serwer zgłosi `app_update` w `/health/ready`, gdy URL nie pasuje do pakietu albo minimum jest ujemne.
3. Razem z tym włącz `PROFILE_UPDATE_REQUIRES_REVISION` (aktualny klient wysyła `expected_revision`).
4. Wycofanie: `MIN_APP_VERSION_CODE=0` wyłącza bramkę natychmiast.
