# Utrzymywane skrypty

Uruchamiaj z katalogu głównego repozytorium, w środowisku z odpowiednimi zależnościami. Bieżąca praca wynika z [planu bety](../docs/epics/E-001-google-play-beta/README.md), a nie z kolejności plików w tym katalogu.

## Kontrole i rozwój

| Plik | Zastosowanie / skutki |
|---|---|
| `ci_check.py` | Zbiorcza kontrola: napisy, LSP, backend pytest |
| `check_ui_strings.py` | Odczyt i walidacja zasobów UI |
| `lsp_sync.py` | Odczyt i kontrola zgodności kluczy LSP/Android |
| `i18n_apply.py` | Zapis tłumaczeń z paczki do plików zasobów |
| `i18n_export_gaps.py` | Eksport braków do lokalnego raportu |
| `i18n_pack.json` | Utrzymywana paczka tłumaczeń, nie wynik jednorazowego testu |
| `translate_ui_strings.py` | Tłumaczenia przez usługę AI; możliwe koszty i zapis plików |
| `lsp_fill_ui_labels.py` | Uzupełnianie etykiet LSP; sprawdź opcje/konfigurację przed uruchomieniem, możliwe koszty i zapis |

## Lokalne środowisko i E2E

| Plik | Zastosowanie / skutki |
|---|---|
| `start-backend.ps1` | Wrapper głównego launchera backendu |
| `start-docker.ps1` | Uruchomienie lokalnego Postgresa/Redis z konfiguracji infra |
| `e2e-maestro.ps1` | Uruchomienie scenariuszy na urządzeniu/emulatorze |
| `e2e-prepare-backend.ps1` | Przygotowanie danych E2E; zapisuje dane testowe |
| `e2e_lang_pairs_test.py` | Scenariusze par językowych; wymaga przeglądu środowiska i może wywoływać API/AI |

Konfiguracja i ograniczenia: [E2E README](../e2e/README.md). Nie kieruj testów ani seedowania na produkcję.

## Utrzymanie danych — nie jest częścią CI

`backfill_word_families.py` służy do wyrównania rodzin słów. Domyślnie wykonuje dry-run; `--apply` zapisuje, `--prod` wybiera bazę produkcyjną. Uruchomienie wymaga osobnego zlecenia, sprawdzenia celu i kopii danych. Nie uruchamiaj „wszystkich skryptów” jako testu.

Jednorazowe probe/hammer/import/repair zostały wycofane z publikowanej zawartości. Lokalne kopie zachowano w ignorowanym `.local/legacy/`; to archiwum eksperymentów, nie wspierany interfejs narzędziowy. Nie są wymagane do budowania aplikacji ani uruchamiania CI.
