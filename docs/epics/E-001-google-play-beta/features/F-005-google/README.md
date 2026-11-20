# F-005 · Logowanie Google

**ID:** `E-001/F-005` · **Status:** `ready` · **Epic:** [E-001](../../README.md).

**Wartość:** nowy i powracający użytkownik bezpiecznie korzysta z właściwej biblioteki, bez niejawnego łączenia kont i błędu po anulowaniu.

## Zakres i akceptacja

- Pełna walidacja tożsamości/audience, bezpieczna jawna polityka łączenia.
- Credential Manager pozostaje bazą; anulowanie i awaria dostawcy są różnymi stanami.
- Nowe/powracające/Google-only/e-mail i wiele/brak kont przechodzą testy na podpisie Play.
- Wspólny [kontrakt konta F-004](../F-004-email-i-hasla/README.md#zatwierdzona-polityka-konta--17112026): Google jest przypięte do stałej tożsamości, nie aktualnej równości e-maili. Zmiana adresu aplikacji zachowuje Google i nie jest cofana przy kolejnym Google loginie.
- Google-only może dodać hasło w E-001/F-004/T-005. Odłączenie Google/hasła przez użytkownika jest poza zakresem bety.
- Dołączenie Google dopuszcza różne adresy po potwierdzeniu obu tożsamości, bez zmiany adresu aplikacji i bez scalenia kont. Odwołuje pozostałe sesje, odnawia bieżącą i zleca zawiadomienie na adres aplikacji.
- Niezweryfikowana zewnętrzna skrzynka konta Google wymaga naszego linku, jeśli Google nie jest wiarygodnym zarządcą tego adresu. Już potwierdzonego adresu aplikacji nie weryfikujemy ponownie.

## Projekt kontraktu

[Google i recent-auth](./tasks/T-001-google-i-laczenie.md#proponowany-kontrakt-techniczny-google-i-recent-auth) opisuje login/link/reauth, walidację/transport/cache, nonce/proof, API/konflikty/atomowość i stany/testy Androida. Limity/retencja F-004/T-003, sesje/journal F-003/T-001 + F-008/T-003 i konto F-006 są zintegrowane w projekcie. Nowy applicationId/certyfikat Play i dowód działania mają gate F-002; `ready` nie znaczy skonfigurowanego OAuth.

**Task:** [E-001/F-005/T-001 · Google i łączenie kont](./tasks/T-001-google-i-laczenie.md) — B-06, `ready`.

**Zależności:** decyzje E-001/F-001/T-001 i sesje E-001/F-003/T-001; końcowa akceptacja po release E-001/F-002/T-001 i integracji Androida E-001/F-003/T-002.

**Poza zakresem:** wymiana Credential Manager bez potrzeby i samodzielne odłączanie metod. **Weryfikacja:** A-06/A-07, S-01…S-14 z F-004 w zakresie Google i prawdziwy build z Play, nie tylko mock. **Dowody:** brak.
