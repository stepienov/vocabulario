# Wydanie Androida (AAB do Google Play)

Krótka instrukcja operatora. Nie zawiera kluczy ani haseł; klucz uploadu jest poza repozytorium.

## Publiczna alpha przed Play

Alpha to osobna, wczesna wersja z możliwymi błędami, pobierana po wdrożeniu przez `https://vocabulario.io/download/alpha`. Link jest publiczny, a aplikacja łączy się z produkcyjnym API. Pakiet `io.vocabulario.alpha` i prywatny klucz alfy są niezależne od `io.vocabulario.app` i przyszłego podpisu Play. Alpha ma nazwę „Vocabulario Alpha” i nie aktualizuje instalacji debug ani przyszłej instalacji z Play. Przed przejściem zsynchronizuj kolejki offline; nie odinstalowuj starej aplikacji przed sprawdzeniem danych.

Klucz alfy jest lokalnie w ignorowanym `.local/alpha-signing/vocabulario-alpha.p12`. Hasło jest w `password.dpapi`, zaszyfrowane Windows DPAPI dla bieżącego konta Windows. Nie jest to kopia zapasowa: po utracie konta lub komputera nie da się go w ten sposób odszyfrować. **Zrób kopię klucza i hasła w osobnym bezpiecznym magazynie**; nie umieszczaj ich w Git, logach ani wiadomościach. Bez klucza i hasła nie podpiszesz aktualizacji alfy. Hasło można na tym samym koncie Windows skopiować bez wyświetlania, a następnie zapisać w menedżerze haseł i wyczyścić schowek:

```powershell
Add-Type -AssemblyName System.Security
$encrypted = [IO.File]::ReadAllBytes((Resolve-Path .local\alpha-signing\password.dpapi))
$plain = [Security.Cryptography.ProtectedData]::Unprotect($encrypted, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
[Text.Encoding]::UTF8.GetString($plain) | Set-Clipboard
[Array]::Clear($plain, 0, $plain.Length)
Remove-Variable plain, encrypted
# Po zapisaniu hasła: Set-Clipboard -Value ''
```

Nowy APK przygotuj ze zmianami aplikacji, zwiększając `VersionCode` względem poprzedniego:

```powershell
.\build-alpha.ps1 -VersionCode 2 -VersionName "0.1.0-alpha.2"
```

Skrypt podpisuje release, sprawdza pakiet, certyfikat, produkcyjne API, wzrost `versionCode` i wyrównanie 16 KB, po czym aktualizuje `backend/app/public_web/downloads/Vocabulario-alpha.apk` i lokalny `dist/Vocabulario.apk`. Do PR trafia tylko pierwszy z nich; kolejne pliki binarne pozostają w historii Git. CI ponownie weryfikuje podpis i wersję, a po merge Railway buduje backend z `backend/` i serwuje plik z tego samego commita. Sam build ani PR nie wdrażają produkcji. Po wdrożeniu sprawdź pobranie i hash pliku. Gdy pliku brak, endpoint zwraca 503 zamiast starego APK.

Logowanie Google wymaga osobnego klienta OAuth Android dla `io.vocabulario.alpha` i SHA-1 `9D:F0:82:D7:46:FC:19:63:9F:F1:E1:2E:9E:19:62:AC:B2:25:0A:8D` w projekcie Google Cloud. Samo dodanie APK ani App Links nie konfiguruje klienta OAuth; dopóki go nie dodano i nie sprawdzono, nie należy przedstawiać logowania Google jako działającego w alfie.

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

Wynik: `android\app\build\outputs\bundle\release\app-release.aab`. Skrypt sprawdza wyrównanie segmentów ELF bibliotek 64-bit. Dla APK sprawdza dodatkowo wyrównanie ZIP nieskompresowanych bibliotek. Wynik dla AAB nie dowodzi wyrównania wygenerowanego APK ani działania na urządzeniu 16 KB: należy sprawdzić także APK z bundletool i wykonać próbę na obrazie 16 KB.

CI buduje testowy AAB z tymczasowym kluczem, uruchamia lint release i sprawdza wyrównanie bibliotek w AAB oraz debug APK. Nie jest to build podpisany produkcyjnie ani test APK wygenerowanego z AAB.

## Co robi build release

- Ruch tylko HTTPS (`usesCleartextTraffic=false`); debug nadal dopuszcza lokalny HTTP.
- Bez kopii zapasowej i transferu danych (sesja, baza i kolejki są związane z kontem i urządzeniem).
- Schemat bazy Room jest eksportowany do `android\app\schemas\` (podstawa pod testy migracji; same testy wymagają urządzenia).
- Bazy Room w wersjach 1–5 nie są automatycznie usuwane: bez ścieżki migracji otwarcie bazy zakończy się błędem, a dane pozostaną na urządzeniu. Migracje 6–12 nadal wymagają weryfikacji na urządzeniu.
- Minifikacja R8 jest wyłączona do czasu testu na urządzeniu; decyzja o jej włączeniu należy do właściciela po próbie na S24.

## Logowanie Google (klienty OAuth)

Projekt Google Cloud **Vocabulario** (`vocabulario-515311`), Platforma uwierzytelniania Google, odbiorcy: zewnętrzni, status **w wersji produkcyjnej** (tylko zakresy podstawowe, bez weryfikacji). Identyfikatory klientów są publiczne, to nie sekrety; tajny klucz klienta webowego nie jest używany (backend tylko sprawdza `aud` tokenu).

| Klient | Typ | Użycie |
|---|---|---|
| `480709179447-nf37u6tirtbbkjlisfabamm3fvrjg82l` | Aplikacja internetowa | `GOOGLE_OAUTH_CLIENT_ID` w Railway i `GOOGLE_WEB_CLIENT_ID` w `android\app\build.gradle.kts` (to ten sam ID, `serverClientId`). |
| `480709179447-rc3kmqaeelc5aiq57l1lfu8i851f5jqd` | Android | Pakiet `com.vocabulario.app` + SHA-1 `android\keystore\debug.keystore` (build debug na S24). |

Do zrobienia po pierwszym uploadzie do Play: dodać **drugi klient Android** dla pakietu `io.vocabulario.app` z SHA-1 z Play Console → Integralność aplikacji → certyfikat podpisywania aplikacji (Play App Signing), oraz osobno z SHA-1 klucza uploadu, jeśli testujesz lokalny build release. Bez tego logowanie Google w buildzie z Play zakończy się błędem.

## Linki konta

Android obsługuje linki HTTPS `vocabulario.io/account/verify-email`, `/account/reset-password` i `/account/change-email`. Token zostaje we fragmencie linku i jest wysyłany dopiero po potwierdzeniu użytkownika, bez sesji aktualnie zalogowanego konta. Strony WWW pozostają dostępne również bez aplikacji.

Weryfikacja App Links wymaga poprawnego `ANDROID_PACKAGE` i SHA-256 certyfikatu podpisującego w `ANDROID_CERT_SHA256` na serwerze. Wariant debug ma inny pakiet i certyfikat; nie należy uznawać testu debug za dowód dla Play. Otwarcie linku, fragment tokenu i powrót do sesji trzeba jeszcze sprawdzić na urządzeniu i w wersji z Play.

## Przejście z buildu debug do Play

Nowy pakiet to osobna instalacja: nie zastąpi debug `com.vocabulario.app` i nie przeniesie jego danych lokalnych. Praca z kolejek debug musi być wysłana (synchronizacja) przed zainstalowaniem wersji z Play; potem logowanie na to samo konto pobiera dane z serwera. Do tego czasu nie odinstalowuj debug.

## Wymuszenie aktualizacji (HTTP 426)

Aplikacja wysyła `X-App-Version-Code`. Gdy serwer ma `MIN_APP_VERSION_CODE` > 0, a żądanie `/api/v1/...` ma niższą (albo brakującą) wersję, odpowiada **426 `app_update_required`**. Aplikacja pokazuje ekran aktualizacji z przyciskiem do własnego wpisu w Play; sesja, biblioteka i kolejki zostają, nic nie jest kasowane ani wylogowywane. Poza bramką zostają: dokumenty prawne, usuwanie konta, potwierdzenia z e-maili, wylogowanie, zdarzenia poczty i `/admin/`.

Kolejność podniesienia minimum:

1. Opublikuj i sprawdź nowy build (wyższy `versionCode`) na właściwym tracku.
2. Ustaw w Railway `ANDROID_PACKAGE` (pakiet release), `APP_UPDATE_URL=https://play.google.com/store/apps/details?id=<pakiet>` i `MIN_APP_VERSION_CODE=<versionCode nowego buildu>`. Serwer zgłosi `app_update` w `/health/ready`, gdy URL nie pasuje do pakietu albo minimum jest ujemne.
3. Razem z tym włącz `PROFILE_UPDATE_REQUIRES_REVISION` (aktualny klient wysyła `expected_revision`).
4. Wycofanie: `MIN_APP_VERSION_CODE=0` wyłącza bramkę natychmiast.
