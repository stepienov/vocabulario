# T-001 · Release AAB i bezpieczna aktualizacja

**ID:** `E-001/F-002/T-001` · **Status:** `ready` · **Priorytet / rozmiar:** P0 / L.  
**Feature:** [Wydanie Play](../README.md). **Źródło:** B-01; F-13/F-14 i [wymogi Play](../../../sources/analiza-2026-11-17.md#9-google-play--co-przygotować-poza-kodem).

## Cel i zakres

Przygotować powtarzalny niedebugowalny release AAB, upload key/Play App Signing, rosnący versionCode, jawny produkcyjny HTTPS i reguły backupu/transferu. Sprawdzić wymagany SDK (36+ w dniu analizy), toolchain, natywne biblioteki i 16 KB na finalnym artefakcie.

**Zależności:** można zacząć przygotowania niezależnie; konfiguracja właściciela Play i decyzje ochrony danych przed finalizacją. Bezpieczna migracja z istniejącego debug wymaga integracji [E-001/F-003/T-002](../../F-003-sesja-i-offline/tasks/T-002-sesja-androida.md), nie blokuje przygotowania buildu.

Konfiguracja konta i weryfikacje mają osobnego właściciela w [E-001/F-002/T-002](./T-002-konfiguracja-play-console.md). Nie powielamy tych operacji ani nie traktujemy gotowego AAB jako dowodu gotowości konta do dystrybucji.

## Decyzje i stan źródeł — 17.11.2026

Właściciel wybrał **nowy applicationId**, internal → closed, zachowanie kont/postępu bety także po premierze. Dokładny identyfikator, nazwa i domena pozostają krokami wykonawczymi przed pierwszym uploadem; nie wymyślamy ich i nie publikujemy pakietu zastępczego, który zostanie na zawsze.

- [Build app](../../../../../../android/app/build.gradle.kts): `com.vocabulario.app`, compile/target 35, min 26, versionCode 1/versionName 0.1.0, jawny tylko wspólny debug key.
- [Toolchain](../../../../../../android/build.gradle.kts): AGP 8.7.3, Kotlin 2.0.21, KSP 2.0.21-1.0.28 i Hilt 2.52; [wrapper](../../../../../../android/gradle/wrapper/gradle-wrapper.properties) Gradle 8.9, Java 17.
- [Manifest](../../../../../../android/app/src/main/AndroidManifest.xml): backup/cleartext włączone i exact-alarm permission; [API URL](../../../../../../android/app/src/main/java/com/vocabulario/app/data/ApiBaseUrl.kt) przyjmuje dowolne niepuste override lub HTTP emulator/LAN. Nie jest to prawidłowy release dla testerów.

## 1. Tożsamość i podpis

1. Przed pierwszym AAB właściciel podaje ostateczny applicationId i potwierdza dostępność w Console. Konfiguracja release wymaga niepustej jawnej wartości; brak = błąd buildu, nie fallback do starego ID. Namespace/pakiety kodu mogą pozostać bez masowej zmiany nazw.
2. Wszystkie authorities, provider authorities, manifest placeholders, App Links, Firebase/Google konfiguracje jeśli występują, tester instrukcja i link Play odwołują się do wybranego ID; szukać rzeczywistych wystąpień, nie podmieniać wszystkiego bez kontekstu.
3. Wygenerować oddzielny upload key i włączyć **Play App Signing** zgodnie z Console. Upload key nie jest kluczem, którym Google podpisuje instalowany pakiet. Bez pliku/hasła w Git; zaszyfrowana kopia i instrukcja odzyskania upload key u właściciela.
4. Google Android OAuth i `assetlinks.json` sprawdzają **app-signing SHA-256** i nowy pakiet. Odciski upload/debug same nie wystarczą. Odcisk internal app sharing może być inny — próbę krytyczną wykonać z normalnego internal track, nie uznać sharing za dowód.
5. Istniejący wspólny debug keystore pozostaje do debug/uzgodnionego przejścia, nie jest recyklingowany do produkcji.
6. VersionCode dodatni, większy niż wszystkie wcześniej wysłane dla wybranego ID. Jawny parametr release, bez wyprowadzania kolidującej wartości z daty. VersionName opisowy. Kolejna poprawka zawsze większy code; nie da się naprawiać dystrybucji przez obniżenie code.

## 2. Toolchain i finalny artefakt

Docelowo minSdk **26 bez zmiany wsparcia**, compile/target **36 co najmniej**, zgodnie z aktualnym wymaganiem Play dla nowej mobilnej aplikacji. W dniu wysłania ponownie sprawdzić Console/politykę. Zmiana target nie oznacza podniesienia minSdk.

AGP 8.7.3/Gradle 8.9 nie zostają przy API 36 „na suppressed warning”. Wybrać stabilne kompatybilne AGP 8.x wspierające API 36; punkt odniesienia [AGP 8.11](https://developer.android.com/build/releases/agp-8-11-0-release-notes) wymaga Gradle 8.13/JDK 17. Aktualizację traktować jako spójny zestaw, z Kotlin/KSP/Hilt zmienianymi tylko gdy potwierdzone wymagania/testy tego wymagają; nie robić niezależnego globalnego upgrade wszystkich zależności. Jeśli wybrany nowszy patch tego zestawu wymaga zmian, zapisać dokładne wersje i wynik Gradle przed merge.

Release: `debuggable=false`, brak debug logów/inspectorów, HTTPS-only. Sprawdzić edge-to-edge/insets/IME i zachowanie na Android 15/16, proces w tle, linki i powiadomienia; sam compile nie weryfikuje zmiany target.

16 KB: wylistować wszystkie transytywne `.so` w zbudowanym AAB i APK generowanym przez bundletool; sprawdzić ELF/zip alignment i uruchomić na obrazie 16 KB. Brak własnego C++ nie dowodzi braku natywnych zależności. Wymóg/daty Play sprawdzić ponownie; projekt bety wymaga poprawnego finalnego artefaktu, nie odroczenia testu do terminu polityki.

Powtarzalna procedura oznacza te same zapisane wejścia/komendy, nie obietnicę bitowo identycznego zipa z różnych środowisk: commit, JDK/Gradle/SDK, lock/version catalogue jeśli istnieją, parametry publiczne i konfiguracja signing. Dowód release: SHA-256 AAB, code/name/ID, scalony manifest, certyfikat publiczny, mapping/symbole, wynik lint/tests i odnośnik do bezpiecznego artefaktu. Sekrety i pełne logi z danymi poza raportem.

## 3. HTTPS, backup i instalacja

- Release wymaga jawnego zatwierdzonego `https://` origin API, bez userinfo, fragmentu, query, prywatnego hosta/localhost i debugowego portu. Oczekiwany base path skonfigurowany jawnie. Walidacja build-time i runtime; wyłączony cleartext w scalonym release manifeście/network security.
- Emulator/LAN HTTP i debug overrides tylko w debug source set/variant. Brak właściwego URL nie może powodować HTTP do `10.0.2.2` ani automatycznego innego backendu. Publiczny OAuth client ID nie jest sekretem ani powodem przesłaniania błędnej konfiguracji.
- `allowBackup=false`; jawne reguły wykluczenia prywatnych danych w legacy `fullBackupContent` i API 31+ `dataExtractionRules` dla cloud backup **i device transfer**. Tokeny, sesja, Room/cache/outbox, właściciel/generation i dowody nie są kopiowane jako nowa sesja.
- Niektóre OEM odmiennie obsługują `allowBackup=false` przy transferze, dlatego nie wystarczy sam manifest. Instalacyjny materiał Keystore nieeksportowalny; odtworzony plik bez poprawnego bindingu nie daje zalogowanego stanu. Stan odzyskiwania/reauth, bez przypisania cache nowemu kontu i bez automatycznego wipe.
- Próby: cloud/ADB gdzie wspierane, device-to-device i utrata Keystore po reinstalacji na dostępnych urządzeniach. Brak fizycznego transferu to jawny BLOCKED tej próby, nie PASS z analizy XML.
- Przypomnienia według F-007 są inexact; usunąć permission exact alarm dopiero razem z migracją/cancel starych alarmów w F-007/T-002, nie samym manifestem.

## 4. Przejście istniejących danych i kolejność wdrożeń

### Obecny debug → nowy pakiet Play

Nowy applicationId to **osobna instalacja**, mogą istnieć obok siebie. Nie obiecywać aktualizacji starego debug APK przez Play; zmiana nazwy nie przenosi Room/Keystore. Nie kazać odinstalować starego przed uzgodnieniem pracy.

1. Zrobić próbę na syntetycznej starej instalacji: właściciel/profil, pending/parked/blocked we wszystkich kolejkach, oceny/undo/moves/lookups i raporty. Stary ogólny „sync OK” nie jest dowodem per-item ACK.
2. Dla obecnych znanych instalacji przed przełączeniem auth przygotować kontrolowaną instrukcję: finalny sync na jeszcze zgodnym backendzie, potwierdzenie obecności własnych danych na serwerze i brak nierozstrzygniętej kolejki; nie tworzyć nowego User przez Google/e-mail o podobnej nazwie.
3. Gdy stary klient nie pozwala potwierdzić pełnej kolejki, przygotować przejściowy build dla **starego ID i podpisu debug**, z bezpiecznym inwentarzem/migracją F-003; nie udawać, że nowy pakiet otworzy pliki starego. Nie zmieniać istniejącego debug key. Ownerless dane pozostają kwarantanną; sam obecny login/adres/JWT nie dowodzi właściciela wszystkich historycznych wierszy.
4. Nierozstrzygnięte pochodzenie lub konflikt → zachować starą instalację i zabezpieczoną lokalną kopię w ramach wsparcia, z odrębną zgodą na kontrolowaną operację danych. Weryfikacja właściciela według F-003; brak dowodu blokuje przypisanie, nie powoduje skasowania. Żadnego automatycznego eksportu bibliotek do repo/chmury ani ręcznego UPDATE owner po adresie.
5. W Play zalogować się na **ten sam backend User.id**, przejść wymaganą weryfikację/warunki i zsynchronizować. Porównać profile/postęp/ustawienia. Dopiero po uzgodnieniu ACK/przeniesienia i świadomej decyzji usunąć stary debug. Lokalny logout nowego pakietu nie usuwa nierozstrzygniętej starej instalacji.

Ograniczenie: istniejący błędny/ownerless zapis nie dostaje wymyślonej historii. Gdy nie da się go bezpiecznie przenieść automatycznie, użytkownik widzi blokadę/obsługę odzyskiwania zamiast pustego sukcesu. Próba syntetyczna i rozwiązanie faktycznie znanych przypadków są gate przed migracją, nie zadaniem „po beta”.

### Backend v2 → klient → następna wersja

Podział dostarczenia: addytywne tabele/pola → test backendu i klienta na staging → przygotowanie przejścia starych instalacji → backend obsługujący sesje/nowe błędy → klient w internal → odbiór i podniesienie minimum → closed. Stare wydanie nie może omijać sesji/weryfikacji/usuwania po przełączeniu; nie zostawiamy legacy JWT endpointu jako „tymczasowej zgodności”.

Metadane wersji klienta służą czytelnemu 426 `app_update_required`, nie są dowodem uprawnień. Zgodność bieżącego i poprzedniego Play klienta utrzymywać do zakończenia testu aktualizacji/uzgodnienia lokalnej pracy; wymuszenie nowego minimum nie kasuje danych i ma ścieżkę pomocy dla długo offline. Publiczne strony praw/usuwania nie są blokowane minimum aplikacji.

Room: addytywne migracje schematu z testami z poprzednich wersji, bez `fallbackToDestructiveMigration`. Upgrade w trakcie requestu, in-flight refresh i pending ACK ma zachować immutable intent/owner/generation. Stary payload nie jest bezwarunkowo przepisywany na aktualną rewizję; konflikty mają wyniki F-003.

Play wersja N → N+1 na tym samym pakiecie/podpisie: wypełniona biblioteka, wszystkie rodzaje niewysłanej pracy, zły/net-offline backend, zmieniona sesja na drugim urządzeniu. Udowodnić zachowanie kolejek i brak podwójnego zastosowania. Backend rollback to kompatybilny kod, nie downgrade DB; Android hotfix ma nowy code.

## 5. Kroki i wynik

L podzielić na sprawdzalne PR-y bez zmiany ID: konfiguracja i toolchain → podpis/artefakt → backup/binding → bridge/migracje → Play install/update. Most właściciela i pełny stan sesji implementuje F-003, nie drugi niezależny AuthRepository.

W katalogu Android użyć istniejącego wrappera: `.\gradlew.bat :app:testDebugUnitTest :app:lintRelease :app:bundleRelease`, po wpisaniu publicznych parametrów release i bezpiecznym podaniu signing. Dokładne warianty testowe dostosować do istniejących tasków Gradle; brak signing/config nie jest zaliczonym release. AAB sprawdzić bundletool/apksigner na generowanym APK, następnie **zainstalować z internal track** i przetestować App Links/Google/upgrade.

Jeśli pomocniczo budowany i zweryfikowany APK do dystrybucji, w `dist/` zostaje tylko najnowszy `Vocabulario.apk`; usuwać wyłącznie stare APK z tego katalogu po potwierdzeniu nowego, nie inne artefakty/klucze. Nie budujemy APK przy samym pisaniu dokumentu.

## Kryteria i weryfikacja

- [ ] Play przyjmuje AAB; zapisano wersję, podpis, URL i scalony manifest; release nie dopuszcza przypadkowego LAN/HTTP.
- [ ] Klucz produkcyjny poza Git, znany właściciel/backup; debug nie jest kluczem produkcji.
- [ ] Tokeny/sesja nie wracają z backupu/transferu; cache/outbox mają jawną politykę właściciela.
- [ ] A-18/A-19: debug → Play ma bezpieczną instrukcję przy niezgodnym podpisie; Play → kolejna wersja zachowuje dane i niewysłane operacje.
- [ ] Wykonano wymagane Gradle/lint/release, instalację i update; wymagania sklepu sprawdzono ponownie.
- [ ] Nowy applicationId świadomie zatwierdzony przed pierwszym uploadem; Google/App Links działają na certyfikacie Play. Namespace nie został zmieniony bez potrzeby.
- [ ] Dowód 16 KB i backup/transfer pochodzi z finalnego artefaktu; upgrade z niewysłaną pracą daje dokładne ACK/wyniki konfliktów.
- [ ] Znane stare instalacje mają uzgodnioną pracę albo bezpieczny zachowany stan odzyskiwania; nie ma instrukcji „odinstaluj i zaloguj się” jako zamiennika migracji.

## Źródła

Sprawdzone 17.11.2026: [wymagany target](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en), [AGP/API 36](https://developer.android.com/build/releases/agp-8-11-0-release-notes), [16 KB](https://developer.android.com/guide/practices/page-sizes), [Play App Signing](https://developer.android.com/studio/publish/app-signing), [backup/transfer](https://developer.android.com/identity/data/autobackup). Daty polityk i wymagania sprawdzamy ponownie przy wysyłce.

**Poza zakresem:** automatyczna publikacja, wybór nazwy/domeny teraz, zmiana podpisu bieżących debug APK i reset beta kont. **Wynik weryfikacji:** analiza konfiguracji i projekt; brak buildu, kluczy, migracji i uploadu.
