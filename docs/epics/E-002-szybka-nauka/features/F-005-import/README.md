# F-005 · Przewidywalny import

**ID:** `E-002/F-005` · **Status:** `verification_required` · **Epic:** [E-002](../../README.md).

**Wartość:** użytkownik zatwierdza ograniczoną listę i widzi postęp; jedna partia nie blokuje bez końca kolejki profilu ani nie mnoży kosztów.

**Task:** [E-002/F-005/T-001 · Import](./tasks/T-001-import.md) — dawniej 11, `verification_required`.

**Zależności:** E-002/F-004/T-001, E-002/F-004/T-002 i E-002/F-004/T-003. Kontrakt importu nadal wiąże kolejkę z gotowością do nauki, nie pełnym `ready`.

## Akceptacja

- Najwyżej 25 pozycji na job i 25 kart importu/profil/dobę UTC, także po formatowaniu i dla różnych źródeł.
- Bez `import_verify`; duplikaty zbiorczo, zapis z SAVEPOINT na pozycję i bez hydracji w pętli.
- Następna karta po `learnable` albo zapisie adaptacyjnym; brak dodatkowego pełnego oczekiwania na resztę karty.
- Zatwierdzanie/anulowanie/wznawianie i współbieżność zgodnie z sekcją „Sprawdzenie” taska, z rzeczywistym PostgreSQL tam, gdzie wymagany.

**Poza zakresem:** zmiana parserów i formatu przy okazji. **Źródło:** [decyzje](../../sources/optymalizacja-requestow.md). **Dowody:** brak nowej weryfikacji; kontrakt zachowany, nie zlecony ponownie.
