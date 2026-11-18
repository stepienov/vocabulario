# F-007 · Prywatność i wsparcie

**ID:** `E-001/F-007` · **Status:** `ready` · **Epic:** [E-001](../../README.md).

**Wartość:** tester rozumie przetwarzanie danych, może dostać pomoc i zgłosić treść, a interfejs nie wyklucza go przez uprawnienia lub dostępność.

## Zakres i akceptacja

- Publiczna polityka, Data safety i deklaracje Play odpowiadają faktycznym danym, SDK, dostawcom i retencji.
- Warunki korzystania z bety i wymagane informacje o usługodawcy mają publiczne wersje, dostęp przed rejestracją i akceptację prawną odpowiednią dla usługi oferowanej z Hiszpanii/UE.
- Wsparcie i zgłoszenie treści są dostępne, potwierdzają przyjęcie i nie wysyłają sekretów/biblioteki automatycznie.
- Dostępność, timeouty, odmowa powiadomień i zachowanie przypomnień mają sprawdzone scenariusze.
- Zgodnie z decyzją beta ma wyłącznie lokalne przypomnienia, bez serwerowego push.
- Osobny publiczny serwis aplikacji udostępnia opis, dokumenty, pomoc i ścieżkę żądania usunięcia; nie wymaga konta w aplikacji.
- Dorośli to grupa docelowa, nie zwolnienie z zasad treści AI i zgłoszeń. Klasyfikację wieku ustalamy według rzeczywistej treści, nie samej etykiety „18+”.

## Stan po zamknięciu decyzji produktu

Zatwierdzono: brak pełnych kopii diagnostycznych, logi techniczne 7 dni, metryki bez treści 30 dni; backupy w Railway do około 30 dni (zmiana 18.11.2026); dopuszczenie obecnych/planowanych dostawców poza EOG po wymaganej weryfikacji; dokumenty/pomoc PL/EN/ES; proste oświadczenie pełnoletności i osobną akceptację warunków; cel pierwszej odpowiedzi człowieka do 2 dni roboczych. Nie oznacza to zakupu, gotowej umowy/polityki ani zmiany kodu.

| Projekt | Zapisane | Co konkretnie pozostaje |
|---|---|---|
| T-001 dane | Przepływy/raw logi/retencja, jawny admission/provenance cache, allowlista i wyjątki; również monitoring | Rzeczywiste konto/model/cennik/DPA/region i zatwierdzenie podstaw/wyjątków przed użyciem; klasyfikacja/cleanup historii po osobnym zleceniu |
| T-002 pomoc/UI | Raport bez LLM, idempotency/offline/receipt/panel, inwentarz powierzchni, polityka, lokalne alarmy/dostępność | Dispatch/ACK F-003, operator-właściciel/e-mail F-008/T-004; prawdziwy kontakt przed zaproszeniem |
| T-003 prawo | Zakres dokumentów, wersje/dowód, akceptacja email/Google/stare konta, legal gate bez utraty pracy i prawa do materiałów | Właściwy przegląd Hiszpania/UE, dane do publikacji i licencje/atrybucja; finalne rynki z F-002 |
| T-004 WWW | Minimalna architektura, publiczne/niezmienne URL, języki, bezpieczne formularze i fallback | Odłożona nazwa/domena, zatwierdzenie hostingu/kosztu i integracji; konfiguracja/realny test przed publikacją |

Cztery projekty po przeglądzie zależności mają `ready`: można wykonywać po zleceniu, ale **nie jest to prawna akceptacja ani gotowa prywatność aplikacji**. F-008 opisuje konkretną izolację/kopie/journal/restore i operatora, F-002 kraj/listing/release; nie są już kolejnymi nieopisanymi blokami. Nie wracamy do wyboru 7+7/języków/supportu.

| ID | Task | Status |
|---|---|---|
| E-001/F-007/T-001 | [Prywatność i deklaracje](./tasks/T-001-prywatnosc-i-deklaracje.md), B-11 | `ready` |
| E-001/F-007/T-002 | [Wsparcie i dostępność](./tasks/T-002-wsparcie-i-dostepnosc.md), B-12 | `ready` |
| E-001/F-007/T-003 | [Warunki bety i informacje prawne](./tasks/T-003-warunki-i-informacje-prawne.md), doprecyzowanie z 17.11.2026 | `ready` |
| E-001/F-007/T-004 | [Publiczny serwis aplikacji](./tasks/T-004-publiczny-serwis-aplikacji.md), doprecyzowanie z 17.11.2026 | `ready` |

**Zależności:** T-001 po decyzjach, finalna zgodność po usuwaniu konta i ustaleniu SDK; T-003 współdzieli inwentaryzację danych i odpowiada za warunki/identyfikację operatora, T-004 za serwis/stałe adresy. T-002 powiązany z sesją Androida i deklaracjami; kontrole wymagane polityką/bezpieczeństwem są bramką bety mimo źródłowego P1.

**Poza zakresem:** marketingowe zgody, server push, nowy helpdesk/SDK analityki i automatyczny LLM oceniający każdy raport. **Weryfikacja:** A-17/A-20…A-22, scenariusze retencji/raportu/akceptacji i działające publiczne adresy. **Dowody:** analiza kodu/publicznych źródeł i decyzje w taskach; bez implementacji/runtime.
