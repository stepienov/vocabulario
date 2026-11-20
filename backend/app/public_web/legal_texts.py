"""Terms and privacy notice drafts (E-001/F-007/T-003, T-001).

DRAFT: written from what the code really does and not yet reviewed by a lawyer. The text may be
published only after the owner confirms the operator data and the legal review. Placeholders
`{operator}`, `{contact}` and `{app}` are filled at render time and are not part of the digest.
Changing any wording means a new version in `app.services.legal_docs`.
"""

from __future__ import annotations

Section = tuple[str, tuple[str, ...]]

DOCUMENTS: dict[str, dict[str, dict[str, object]]] = {
    "terms": {
        "en": {
            "title": "Terms of Use",
            "sections": (
                (
                    "1. Who provides {app}",
                    (
                        "{app} is a vocabulary learning app provided by {operator} "
                        "(contact: {contact}). The closed beta is offered for testing.",
                    ),
                ),
                (
                    "2. Eligibility",
                    (
                        "You must be at least 18 years old to create an account. "
                        "You confirm this when you register.",
                    ),
                ),
                (
                    "3. Your account",
                    (
                        "Keep your password and your Google account secure. You are responsible "
                        "for activity under your account. You can delete the account at any time "
                        "in the app or at /delete-account.",
                    ),
                ),
                (
                    "4. Acceptable use",
                    (
                        "Do not misuse the service: no attempts to break it, overload it, or "
                        "enter unlawful, offensive or other people's private data. Do not put "
                        "passwords or secrets into notes, imports or reports.",
                    ),
                ),
                (
                    "5. AI-generated content",
                    (
                        "Meanings, examples and exercises are produced with the help of automated "
                        "language models and may be inaccurate. Check important content "
                        "yourself. You can report wrong or inappropriate content in the app.",
                    ),
                ),
                (
                    "6. Beta service",
                    (
                        "The service is a beta version. It may change, be interrupted or lose "
                        "data despite our care. We do not promise uninterrupted availability.",
                    ),
                ),
                (
                    "7. Liability",
                    (
                        "Nothing in these terms limits liability that cannot be limited by law, "
                        "including your mandatory consumer rights.",
                    ),
                ),
                (
                    "8. Changes and contact",
                    (
                        "If these terms change, the app asks you to accept the new version "
                        "before you continue. Questions: {contact}.",
                    ),
                ),
            ),
        },
        "pl": {
            "title": "Regulamin",
            "sections": (
                (
                    "1. Kto udostępnia {app}",
                    (
                        "{app} to aplikacja do nauki słownictwa udostępniana przez {operator} "
                        "(kontakt: {contact}). Zamknięta beta służy do testów.",
                    ),
                ),
                (
                    "2. Wiek",
                    (
                        "Konto może założyć osoba, która ukończyła 18 lat. "
                        "Potwierdzasz to przy rejestracji.",
                    ),
                ),
                (
                    "3. Twoje konto",
                    (
                        "Chroń hasło i konto Google. Odpowiadasz za działania na swoim koncie. "
                        "Konto możesz w każdej chwili usunąć w aplikacji albo na stronie "
                        "/delete-account.",
                    ),
                ),
                (
                    "4. Zasady korzystania",
                    (
                        "Nie nadużywaj usługi: nie próbuj jej psuć ani przeciążać, nie wpisuj "
                        "treści niezgodnych z prawem, obraźliwych ani cudzych danych prywatnych. "
                        "Nie wpisuj haseł ani sekretów w notatkach, importach i zgłoszeniach.",
                    ),
                ),
                (
                    "5. Treści generowane przez AI",
                    (
                        "Znaczenia, przykłady i ćwiczenia powstają z pomocą automatycznych modeli "
                        "językowych i mogą być niedokładne. Ważne treści sprawdzaj samodzielnie. "
                        "Błędną lub niewłaściwą treść możesz zgłosić w aplikacji.",
                    ),
                ),
                (
                    "6. Wersja beta",
                    (
                        "Usługa jest w wersji beta. Może się zmieniać, być niedostępna albo, mimo "
                        "naszej staranności, utracić dane. Nie obiecujemy ciągłej dostępności.",
                    ),
                ),
                (
                    "7. Odpowiedzialność",
                    (
                        "Żaden zapis regulaminu nie ogranicza odpowiedzialności, której prawo nie "
                        "pozwala ograniczyć, w tym Twoich obowiązkowych praw konsumenta.",
                    ),
                ),
                (
                    "8. Zmiany i kontakt",
                    (
                        "Gdy regulamin się zmieni, aplikacja poprosi o akceptację nowej wersji "
                        "przed dalszym korzystaniem. Pytania: {contact}.",
                    ),
                ),
            ),
        },
        "es": {
            "title": "Condiciones de uso",
            "sections": (
                (
                    "1. Quién ofrece {app}",
                    (
                        "{app} es una aplicación para aprender vocabulario ofrecida por "
                        "{operator} (contacto: {contact}). La beta cerrada se ofrece para pruebas.",
                    ),
                ),
                (
                    "2. Edad",
                    (
                        "Debes tener al menos 18 años para crear una cuenta. "
                        "Lo confirmas al registrarte.",
                    ),
                ),
                (
                    "3. Tu cuenta",
                    (
                        "Protege tu contraseña y tu cuenta de Google. Eres responsable de la "
                        "actividad de tu cuenta. Puedes eliminarla en cualquier momento en la "
                        "aplicación o en /delete-account.",
                    ),
                ),
                (
                    "4. Uso aceptable",
                    (
                        "No uses mal el servicio: no intentes dañarlo ni sobrecargarlo, ni "
                        "introduzcas contenido ilícito, ofensivo o datos privados de otras "
                        "personas. No escribas contraseñas ni secretos en notas, importaciones "
                        "o informes.",
                    ),
                ),
                (
                    "5. Contenido generado por IA",
                    (
                        "Los significados, ejemplos y ejercicios se crean con ayuda de modelos "
                        "de lenguaje automáticos y pueden ser inexactos. Verifica por tu cuenta "
                        "el contenido importante. Puedes informar de contenido erróneo o "
                        "inapropiado en la aplicación.",
                    ),
                ),
                (
                    "6. Servicio beta",
                    (
                        "El servicio es una versión beta. Puede cambiar, interrumpirse o perder "
                        "datos a pesar de nuestro cuidado. No prometemos disponibilidad continua.",
                    ),
                ),
                (
                    "7. Responsabilidad",
                    (
                        "Ninguna cláusula limita la responsabilidad que la ley no permite "
                        "limitar, incluidos tus derechos obligatorios como consumidor.",
                    ),
                ),
                (
                    "8. Cambios y contacto",
                    (
                        "Si cambian estas condiciones, la aplicación te pedirá aceptar la nueva "
                        "versión antes de continuar. Preguntas: {contact}.",
                    ),
                ),
            ),
        },
    },
    "privacy": {
        "en": {
            "title": "Privacy Notice",
            "sections": (
                (
                    "1. Controller",
                    ("{operator} ({contact}) decides how your data is used in {app}.",),
                ),
                (
                    "2. Data we process and why",
                    (
                        "Account: e-mail address, password hash or Google identifier, sign-in "
                        "sessions. Purpose: providing the account (contract).",
                        "Learning: words you look up or import, cards, lists, review history and "
                        "settings. Purpose: providing the app and syncing between your devices.",
                        "Technical logs: request type, status and time, without e-mail, IP "
                        "address, full URL or the text you search. Purpose: security and "
                        "stability (legitimate interest).",
                        "Support: content reports and messages you send. Purpose: handling them.",
                    ),
                ),
                (
                    "3. Recipients",
                    (
                        "Hosting (Railway), a language model provider (OpenAI; receives the word "
                        "or text needed for one request), e-mail delivery (Resend) and Google "
                        "when you choose Google sign-in. We do not sell data and use no "
                        "advertising or analytics SDK.",
                    ),
                ),
                (
                    "4. Retention",
                    (
                        "Technical logs: 7 days. Cost metrics without content: 30 days. Account "
                        "data until you delete the account. After a deletion request you have 7 "
                        "days to cancel; active data is then removed within 14 days at the "
                        "latest. Backups expire within about 30 days.",
                    ),
                ),
                (
                    "5. Your rights",
                    (
                        "You can access, correct, delete and export your data and object to "
                        "processing. Delete the account in the app or at /delete-account. "
                        "Contact {contact} for any request. You may complain to your data "
                        "protection authority.",
                    ),
                ),
                (
                    "6. Transfers and age",
                    (
                        "Some providers process data outside the EU under appropriate "
                        "safeguards. The app is for adults (18+).",
                    ),
                ),
            ),
        },
        "pl": {
            "title": "Polityka prywatności",
            "sections": (
                (
                    "1. Administrator",
                    ("{operator} ({contact}) decyduje, jak są używane Twoje dane w {app}.",),
                ),
                (
                    "2. Jakie dane przetwarzamy i po co",
                    (
                        "Konto: adres e-mail, skrót hasła lub identyfikator Google, sesje "
                        "logowania. Cel: prowadzenie konta (umowa).",
                        "Nauka: wyszukiwane lub importowane słowa, fiszki, listy, historia "
                        "powtórek i ustawienia. Cel: działanie aplikacji i synchronizacja "
                        "między urządzeniami.",
                        "Logi techniczne: typ żądania, status i czas, bez e-maila, adresu IP, "
                        "pełnego URL i wyszukiwanego tekstu. Cel: bezpieczeństwo i stabilność "
                        "(prawnie uzasadniony interes).",
                        "Wsparcie: zgłoszenia treści i wiadomości, które wysyłasz. Cel: ich "
                        "obsługa.",
                    ),
                ),
                (
                    "3. Odbiorcy",
                    (
                        "Hosting (Railway), dostawca modelu językowego (OpenAI; dostaje słowo lub "
                        "tekst potrzebny do jednego zapytania), wysyłka e-mail (Resend) oraz "
                        "Google, gdy wybierzesz logowanie Google. Nie sprzedajemy danych i nie "
                        "używamy SDK reklamowych ani analitycznych.",
                    ),
                ),
                (
                    "4. Okresy przechowywania",
                    (
                        "Logi techniczne: 7 dni. Metryki kosztów bez treści: 30 dni. Dane konta "
                        "do czasu jego usunięcia. Po zgłoszeniu usunięcia masz 7 dni na "
                        "wycofanie; aktywne dane usuwamy najpóźniej w ciągu kolejnych 7 dni "
                        "(łącznie do 14 dni). Kopie zapasowe wygasają w ok. 30 dni.",
                    ),
                ),
                (
                    "5. Twoje prawa",
                    (
                        "Masz prawo dostępu, sprostowania, usunięcia, przenoszenia danych oraz "
                        "sprzeciwu. Konto usuniesz w aplikacji albo na stronie /delete-account. "
                        "W każdej sprawie pisz na {contact}. Możesz złożyć skargę do organu "
                        "ochrony danych.",
                    ),
                ),
                (
                    "6. Transfery i wiek",
                    (
                        "Niektórzy dostawcy przetwarzają dane poza UE z odpowiednimi "
                        "zabezpieczeniami. Aplikacja jest dla dorosłych (18+).",
                    ),
                ),
            ),
        },
        "es": {
            "title": "Aviso de privacidad",
            "sections": (
                (
                    "1. Responsable",
                    ("{operator} ({contact}) decide cómo se usan tus datos en {app}.",),
                ),
                (
                    "2. Datos que tratamos y para qué",
                    (
                        "Cuenta: correo electrónico, hash de la contraseña o identificador de "
                        "Google, sesiones. Finalidad: prestar la cuenta (contrato).",
                        "Aprendizaje: palabras que buscas o importas, tarjetas, listas, "
                        "historial de repasos y ajustes. Finalidad: ofrecer la aplicación y "
                        "sincronizar tus dispositivos.",
                        "Registros técnicos: tipo de petición, estado y hora, sin correo, "
                        "dirección IP, URL completa ni el texto que buscas. Finalidad: "
                        "seguridad y estabilidad (interés legítimo).",
                        "Soporte: informes de contenido y mensajes que envías. Finalidad: "
                        "atenderlos.",
                    ),
                ),
                (
                    "3. Destinatarios",
                    (
                        "Alojamiento (Railway), proveedor de modelos de lenguaje (OpenAI; recibe "
                        "la palabra o el texto necesario para una petición), envío de correo "
                        "(Resend) y Google si eliges iniciar sesión con Google. No vendemos "
                        "datos ni usamos SDK de publicidad o analítica.",
                    ),
                ),
                (
                    "4. Plazos de conservación",
                    (
                        "Registros técnicos: 7 días. Métricas de coste sin contenido: 30 días. "
                        "Datos de la cuenta hasta que la elimines. Tras solicitar la "
                        "eliminación tienes 7 días para cancelarla; los datos activos se borran "
                        "como máximo en los 7 días siguientes (14 en total). Las copias de "
                        "seguridad caducan en unos 30 días.",
                    ),
                ),
                (
                    "5. Tus derechos",
                    (
                        "Puedes acceder, rectificar, suprimir y portar tus datos y oponerte al "
                        "tratamiento. Elimina la cuenta en la aplicación o en /delete-account. "
                        "Escribe a {contact} para cualquier solicitud. Puedes reclamar ante tu "
                        "autoridad de protección de datos.",
                    ),
                ),
                (
                    "6. Transferencias y edad",
                    (
                        "Algunos proveedores tratan datos fuera de la UE con garantías "
                        "adecuadas. La aplicación es para adultos (18+).",
                    ),
                ),
            ),
        },
    },
}
