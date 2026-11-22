"""Texts of the one-time account pages; same locales and tone as the e-mail templates."""

from __future__ import annotations

from app.public_web.texts_deletion import (
    BROWSER_KEYS, BROWSER_RECEIPT_TEXTS, BROWSER_TEXTS, DELETION_KEYS, DELETION_TEXTS,
)

KEYS = (
    "verify_title",
    "verify_intro",
    "verify_button",
    "verify_done",
    "reset_title",
    "reset_intro",
    "new_password",
    "confirm_password",
    "password_hint",
    "show_password",
    "reset_button",
    "mismatch",
    "too_short",
    "too_long",
    "invalid_unicode",
    "reset_done",
    "noscript",
    "missing_token",
    "invalid",
    "expired",
    "used",
    "network",
    "rate_limited",
    "error",
    "working",
    "change_title",
    "change_intro",
    "change_button",
    "change_done",
    "change_unavailable",
)

PAGE_TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "change_title": "Confirm your new email address",
        "change_intro": "Press the button below to change the email address of your {app} account to the one this link was sent to. You will be signed out on all devices.",
        "change_button": "Confirm new address",
        "change_done": "Done! Your email address is changed. Sign in to the app again with the new address.",
        "change_unavailable": "This address can no longer be used for this account. Start the change again in the app.",
        "verify_title": "Confirm your email address",
        "verify_intro": (
            "Press the button below to confirm that this is the email address of your "
            "{app} account."
        ),
        "verify_button": "Confirm address",
        "verify_done": "Done! Your email address is confirmed. You can go back to the app.",
        "reset_title": "Set a new password",
        "reset_intro": (
            "Choose a new password for your {app} account. After saving, you will be signed "
            "out on all devices."
        ),
        "new_password": "New password",
        "confirm_password": "Repeat new password",
        "password_hint": "At least {min} characters. A few unrelated words work well.",
        "show_password": "Show passwords",
        "reset_button": "Save new password",
        "mismatch": "The passwords do not match.",
        "too_short": "The password must have at least {min} characters.",
        "too_long": "The password can have at most {max} characters.",
        "invalid_unicode": "The password contains characters that cannot be used.",
        "reset_done": "Your password has been changed. Sign in to the app with your new password.",
        "noscript": "This page needs JavaScript to finish. Turn it on and open the link again.",
        "missing_token": (
            "This link is incomplete. Open it again from the email or request a new one in the app."
        ),
        "invalid": "This link is no longer valid. Request a new one in the app.",
        "expired": "This link has expired. Request a new one in the app.",
        "used": "This link has already been used. If it was you, the change is already saved.",
        "network": "Could not connect. Check your internet connection and try again.",
        "rate_limited": "Too many attempts. Wait a moment and try again.",
        "error": "Something went wrong. Try again in a moment.",
        "working": "Please wait…",
    },
    "es": {
        "change_title": "Confirma tu nueva dirección de correo",
        "change_intro": "Pulsa el botón para cambiar la dirección de correo de tu cuenta de {app} a la que recibió este enlace. Se cerrará la sesión en todos los dispositivos.",
        "change_button": "Confirmar nueva dirección",
        "change_done": "¡Listo! Tu dirección de correo ha cambiado. Inicia sesión de nuevo en la aplicación con la nueva dirección.",
        "change_unavailable": "Esta dirección ya no se puede usar para esta cuenta. Inicia el cambio de nuevo en la aplicación.",
        "verify_title": "Confirma tu dirección de correo",
        "verify_intro": (
            "Pulsa el botón para confirmar que esta es la dirección de correo de tu cuenta "
            "de {app}."
        ),
        "verify_button": "Confirmar dirección",
        "verify_done": (
            "¡Listo! Tu dirección de correo está confirmada. Ya puedes volver a la aplicación."
        ),
        "reset_title": "Establece una nueva contraseña",
        "reset_intro": (
            "Elige una nueva contraseña para tu cuenta de {app}. Al guardarla, se cerrará la "
            "sesión en todos los dispositivos."
        ),
        "new_password": "Nueva contraseña",
        "confirm_password": "Repite la nueva contraseña",
        "password_hint": (
            "Al menos {min} caracteres. Unas cuantas palabras sin relación funcionan bien."
        ),
        "show_password": "Mostrar contraseñas",
        "reset_button": "Guardar nueva contraseña",
        "mismatch": "Las contraseñas no coinciden.",
        "too_short": "La contraseña debe tener al menos {min} caracteres.",
        "too_long": "La contraseña puede tener como máximo {max} caracteres.",
        "invalid_unicode": "La contraseña contiene caracteres que no se pueden usar.",
        "reset_done": (
            "Tu contraseña se ha cambiado. Inicia sesión en la aplicación con la nueva contraseña."
        ),
        "noscript": (
            "Esta página necesita JavaScript para terminar. Actívalo y vuelve a abrir el enlace."
        ),
        "missing_token": (
            "Este enlace está incompleto. Ábrelo de nuevo desde el correo o solicita uno nuevo "
            "en la aplicación."
        ),
        "invalid": "Este enlace ya no es válido. Solicita uno nuevo en la aplicación.",
        "expired": "Este enlace ha caducado. Solicita uno nuevo en la aplicación.",
        "used": "Este enlace ya se ha utilizado. Si fuiste tú, el cambio ya está guardado.",
        "network": (
            "No se ha podido conectar. Comprueba tu conexión a internet e inténtalo de nuevo."
        ),
        "rate_limited": "Demasiados intentos. Espera un momento e inténtalo de nuevo.",
        "error": "Algo ha salido mal. Inténtalo de nuevo en un momento.",
        "working": "Espera un momento…",
    },
    "pl": {
        "change_title": "Potwierdź nowy adres e-mail",
        "change_intro": "Naciśnij przycisk, aby zmienić adres e-mail konta {app} na ten, na który wysłano link. Zostaniesz wylogowany na wszystkich urządzeniach.",
        "change_button": "Potwierdź nowy adres",
        "change_done": "Gotowe! Adres e-mail został zmieniony. Zaloguj się w aplikacji ponownie nowym adresem.",
        "change_unavailable": "Ten adres nie może już być użyty dla tego konta. Rozpocznij zmianę ponownie w aplikacji.",
        "verify_title": "Potwierdź adres e-mail",
        "verify_intro": (
            "Naciśnij przycisk poniżej, aby potwierdzić, że to adres e-mail Twojego konta w {app}."
        ),
        "verify_button": "Potwierdź adres",
        "verify_done": "Gotowe! Twój adres e-mail jest potwierdzony. Możesz wrócić do aplikacji.",
        "reset_title": "Ustaw nowe hasło",
        "reset_intro": (
            "Wybierz nowe hasło do konta w {app}. Po zapisaniu zostaniesz wylogowany na "
            "wszystkich urządzeniach."
        ),
        "new_password": "Nowe hasło",
        "confirm_password": "Powtórz nowe hasło",
        "password_hint": (
            "Co najmniej {min} znaków. Dobrze sprawdza się kilka niezwiązanych ze sobą słów."
        ),
        "show_password": "Pokaż hasła",
        "reset_button": "Zapisz nowe hasło",
        "mismatch": "Hasła nie są takie same.",
        "too_short": "Hasło musi mieć co najmniej {min} znaków.",
        "too_long": "Hasło może mieć najwyżej {max} znaków.",
        "invalid_unicode": "Hasło zawiera znaki, których nie można użyć.",
        "reset_done": "Hasło zostało zmienione. Zaloguj się w aplikacji nowym hasłem.",
        "noscript": (
            "Ta strona potrzebuje JavaScriptu, aby dokończyć operację. Włącz go i otwórz link "
            "ponownie."
        ),
        "missing_token": (
            "Ten link jest niepełny. Otwórz go ponownie z maila albo poproś o nowy w aplikacji."
        ),
        "invalid": "Ten link jest już nieważny. Poproś o nowy w aplikacji.",
        "expired": "Ten link wygasł. Poproś o nowy w aplikacji.",
        "used": "Ten link został już użyty. Jeśli to Ty, zmiana jest już zapisana.",
        "network": "Nie udało się połączyć. Sprawdź połączenie z internetem i spróbuj ponownie.",
        "rate_limited": "Zbyt wiele prób. Odczekaj chwilę i spróbuj ponownie.",
        "error": "Coś poszło nie tak. Spróbuj ponownie za chwilę.",
        "working": "Proszę czekać…",
    },
    "de": {
        "change_title": "Bestätige deine neue E-Mail-Adresse",
        "change_intro": "Tippe auf die Schaltfläche, um die E-Mail-Adresse deines {app}-Kontos auf die Adresse zu ändern, an die dieser Link gesendet wurde. Du wirst auf allen Geräten abgemeldet.",
        "change_button": "Neue Adresse bestätigen",
        "change_done": "Fertig! Deine E-Mail-Adresse wurde geändert. Melde dich in der App mit der neuen Adresse neu an.",
        "change_unavailable": "Diese Adresse kann für dieses Konto nicht mehr verwendet werden. Starte die Änderung in der App neu.",
        "verify_title": "Bestätige deine E-Mail-Adresse",
        "verify_intro": (
            "Tippe auf die Schaltfläche, um zu bestätigen, dass dies die E-Mail-Adresse deines "
            "{app}-Kontos ist."
        ),
        "verify_button": "Adresse bestätigen",
        "verify_done": (
            "Fertig! Deine E-Mail-Adresse ist bestätigt. Du kannst jetzt zur App zurückkehren."
        ),
        "reset_title": "Neues Passwort festlegen",
        "reset_intro": (
            "Wähle ein neues Passwort für dein {app}-Konto. Nach dem Speichern wirst du auf "
            "allen Geräten abgemeldet."
        ),
        "new_password": "Neues Passwort",
        "confirm_password": "Neues Passwort wiederholen",
        "password_hint": (
            "Mindestens {min} Zeichen. Ein paar zusammenhanglose Wörter eignen sich gut."
        ),
        "show_password": "Passwörter anzeigen",
        "reset_button": "Neues Passwort speichern",
        "mismatch": "Die Passwörter stimmen nicht überein.",
        "too_short": "Das Passwort muss mindestens {min} Zeichen haben.",
        "too_long": "Das Passwort darf höchstens {max} Zeichen haben.",
        "invalid_unicode": "Das Passwort enthält Zeichen, die nicht verwendet werden können.",
        "reset_done": (
            "Dein Passwort wurde geändert. Melde dich in der App mit dem neuen Passwort an."
        ),
        "noscript": "Diese Seite benötigt JavaScript. Aktiviere es und öffne den Link erneut.",
        "missing_token": (
            "Dieser Link ist unvollständig. Öffne ihn erneut aus der E-Mail oder fordere in "
            "der App einen neuen an."
        ),
        "invalid": "Dieser Link ist nicht mehr gültig. Fordere in der App einen neuen an.",
        "expired": "Dieser Link ist abgelaufen. Fordere in der App einen neuen an.",
        "used": (
            "Dieser Link wurde bereits verwendet. Wenn du das warst, ist die Änderung bereits "
            "gespeichert."
        ),
        "network": (
            "Keine Verbindung möglich. Prüfe deine Internetverbindung und versuche es erneut."
        ),
        "rate_limited": "Zu viele Versuche. Warte einen Moment und versuche es erneut.",
        "error": "Etwas ist schiefgelaufen. Versuche es gleich noch einmal.",
        "working": "Bitte warten…",
    },
    "fr": {
        "change_title": "Confirmez votre nouvelle adresse e-mail",
        "change_intro": "Appuyez sur le bouton pour remplacer l'adresse e-mail de votre compte {app} par celle à laquelle ce lien a été envoyé. Vous serez déconnecté de tous les appareils.",
        "change_button": "Confirmer la nouvelle adresse",
        "change_done": "C'est fait ! Votre adresse e-mail a été modifiée. Reconnectez-vous à l'application avec la nouvelle adresse.",
        "change_unavailable": "Cette adresse ne peut plus être utilisée pour ce compte. Recommencez le changement dans l'application.",
        "verify_title": "Confirmez votre adresse e-mail",
        "verify_intro": (
            "Appuyez sur le bouton ci-dessous pour confirmer qu'il s'agit bien de l'adresse "
            "e-mail de votre compte {app}."
        ),
        "verify_button": "Confirmer l'adresse",
        "verify_done": (
            "C'est fait ! Votre adresse e-mail est confirmée. Vous pouvez revenir à l'application."
        ),
        "reset_title": "Définissez un nouveau mot de passe",
        "reset_intro": (
            "Choisissez un nouveau mot de passe pour votre compte {app}. Après l'enregistrement, "
            "vous serez déconnecté de tous vos appareils."
        ),
        "new_password": "Nouveau mot de passe",
        "confirm_password": "Répétez le nouveau mot de passe",
        "password_hint": (
            "Au moins {min} caractères. Quelques mots sans rapport entre eux font l'affaire."
        ),
        "show_password": "Afficher les mots de passe",
        "reset_button": "Enregistrer le nouveau mot de passe",
        "mismatch": "Les mots de passe ne correspondent pas.",
        "too_short": "Le mot de passe doit comporter au moins {min} caractères.",
        "too_long": "Le mot de passe peut comporter au maximum {max} caractères.",
        "invalid_unicode": (
            "Le mot de passe contient des caractères qui ne peuvent pas être utilisés."
        ),
        "reset_done": (
            "Votre mot de passe a été modifié. Connectez-vous à l'application avec le nouveau "
            "mot de passe."
        ),
        "noscript": (
            "Cette page a besoin de JavaScript pour terminer. Activez-le et rouvrez le lien."
        ),
        "missing_token": (
            "Ce lien est incomplet. Rouvrez-le depuis l'e-mail ou demandez-en un nouveau dans "
            "l'application."
        ),
        "invalid": "Ce lien n'est plus valide. Demandez-en un nouveau dans l'application.",
        "expired": "Ce lien a expiré. Demandez-en un nouveau dans l'application.",
        "used": (
            "Ce lien a déjà été utilisé. Si c'était vous, la modification est déjà enregistrée."
        ),
        "network": "Connexion impossible. Vérifiez votre connexion Internet et réessayez.",
        "rate_limited": "Trop de tentatives. Patientez un instant et réessayez.",
        "error": "Une erreur s'est produite. Réessayez dans un instant.",
        "working": "Veuillez patienter…",
    },
    "it": {
        "change_title": "Conferma il tuo nuovo indirizzo e-mail",
        "change_intro": "Premi il pulsante per cambiare l'indirizzo e-mail del tuo account {app} in quello a cui è stato inviato questo link. Verrai disconnesso da tutti i dispositivi.",
        "change_button": "Conferma il nuovo indirizzo",
        "change_done": "Fatto! Il tuo indirizzo e-mail è stato modificato. Accedi di nuovo all'app con il nuovo indirizzo.",
        "change_unavailable": "Questo indirizzo non può più essere usato per questo account. Ripeti la modifica nell'app.",
        "verify_title": "Conferma il tuo indirizzo email",
        "verify_intro": (
            "Premi il pulsante qui sotto per confermare che questo è l'indirizzo email del tuo "
            "account {app}."
        ),
        "verify_button": "Conferma indirizzo",
        "verify_done": "Fatto! Il tuo indirizzo email è confermato. Puoi tornare all'app.",
        "reset_title": "Imposta una nuova password",
        "reset_intro": (
            "Scegli una nuova password per il tuo account {app}. Dopo il salvataggio verrai "
            "disconnesso da tutti i dispositivi."
        ),
        "new_password": "Nuova password",
        "confirm_password": "Ripeti la nuova password",
        "password_hint": (
            "Almeno {min} caratteri. Alcune parole senza relazione tra loro vanno bene."
        ),
        "show_password": "Mostra le password",
        "reset_button": "Salva la nuova password",
        "mismatch": "Le password non coincidono.",
        "too_short": "La password deve avere almeno {min} caratteri.",
        "too_long": "La password può avere al massimo {max} caratteri.",
        "invalid_unicode": "La password contiene caratteri che non possono essere usati.",
        "reset_done": "La password è stata cambiata. Accedi all'app con la nuova password.",
        "noscript": (
            "Questa pagina ha bisogno di JavaScript per completare l'operazione. Attivalo e "
            "riapri il link."
        ),
        "missing_token": (
            "Questo link è incompleto. Riaprilo dall'email o richiedine uno nuovo nell'app."
        ),
        "invalid": "Questo link non è più valido. Richiedine uno nuovo nell'app.",
        "expired": "Questo link è scaduto. Richiedine uno nuovo nell'app.",
        "used": "Questo link è già stato usato. Se sei stato tu, la modifica è già salvata.",
        "network": "Impossibile connettersi. Controlla la connessione a internet e riprova.",
        "rate_limited": "Troppi tentativi. Attendi un momento e riprova.",
        "error": "Qualcosa è andato storto. Riprova tra un momento.",
        "working": "Attendi…",
    },
    "pt-BR": {
        "change_title": "Confirme seu novo endereço de e-mail",
        "change_intro": "Toque no botão para trocar o e-mail da sua conta {app} pelo endereço que recebeu este link. Você será desconectado de todos os dispositivos.",
        "change_button": "Confirmar novo endereço",
        "change_done": "Pronto! Seu endereço de e-mail foi alterado. Entre no app de novo com o novo endereço.",
        "change_unavailable": "Este endereço não pode mais ser usado nesta conta. Inicie a mudança de novo no app.",
        "verify_title": "Confirme seu endereço de e-mail",
        "verify_intro": (
            "Toque no botão abaixo para confirmar que este é o e-mail da sua conta do {app}."
        ),
        "verify_button": "Confirmar endereço",
        "verify_done": "Pronto! Seu e-mail foi confirmado. Você já pode voltar para o app.",
        "reset_title": "Defina uma nova senha",
        "reset_intro": (
            "Escolha uma nova senha para sua conta do {app}. Depois de salvar, você será "
            "desconectado de todos os dispositivos."
        ),
        "new_password": "Nova senha",
        "confirm_password": "Repita a nova senha",
        "password_hint": (
            "Pelo menos {min} caracteres. Algumas palavras sem relação entre si funcionam bem."
        ),
        "show_password": "Mostrar senhas",
        "reset_button": "Salvar nova senha",
        "mismatch": "As senhas não coincidem.",
        "too_short": "A senha precisa ter pelo menos {min} caracteres.",
        "too_long": "A senha pode ter no máximo {max} caracteres.",
        "invalid_unicode": "A senha contém caracteres que não podem ser usados.",
        "reset_done": "Sua senha foi alterada. Entre no app com a nova senha.",
        "noscript": (
            "Esta página precisa de JavaScript para concluir. Ative-o e abra o link de novo."
        ),
        "missing_token": (
            "Este link está incompleto. Abra-o novamente pelo e-mail ou solicite um novo no app."
        ),
        "invalid": "Este link não é mais válido. Solicite um novo no app.",
        "expired": "Este link expirou. Solicite um novo no app.",
        "used": "Este link já foi usado. Se foi você, a alteração já está salva.",
        "network": (
            "Não foi possível conectar. Verifique sua conexão com a internet e tente de novo."
        ),
        "rate_limited": "Muitas tentativas. Aguarde um momento e tente de novo.",
        "error": "Algo deu errado. Tente de novo em instantes.",
        "working": "Aguarde…",
    },
    "pt-PT": {
        "change_title": "Confirme o seu novo endereço de e-mail",
        "change_intro": "Toque no botão para trocar o e-mail da sua conta {app} pelo endereço que recebeu esta ligação. Será desligado de todos os dispositivos.",
        "change_button": "Confirmar novo endereço",
        "change_done": "Feito! O seu endereço de e-mail foi alterado. Inicie sessão de novo na aplicação com o novo endereço.",
        "change_unavailable": "Este endereço já não pode ser usado nesta conta. Inicie a alteração de novo na aplicação.",
        "verify_title": "Confirme o seu endereço de e-mail",
        "verify_intro": (
            "Toque no botão abaixo para confirmar que este é o e-mail da sua conta {app}."
        ),
        "verify_button": "Confirmar endereço",
        "verify_done": "Concluído! O seu e-mail está confirmado. Já pode voltar à aplicação.",
        "reset_title": "Defina uma nova palavra-passe",
        "reset_intro": (
            "Escolha uma nova palavra-passe para a sua conta {app}. Depois de guardar, terminará "
            "a sessão em todos os dispositivos."
        ),
        "new_password": "Nova palavra-passe",
        "confirm_password": "Repita a nova palavra-passe",
        "password_hint": (
            "Pelo menos {min} caracteres. Algumas palavras sem relação entre si funcionam bem."
        ),
        "show_password": "Mostrar palavras-passe",
        "reset_button": "Guardar nova palavra-passe",
        "mismatch": "As palavras-passe não coincidem.",
        "too_short": "A palavra-passe tem de ter pelo menos {min} caracteres.",
        "too_long": "A palavra-passe pode ter no máximo {max} caracteres.",
        "invalid_unicode": "A palavra-passe contém caracteres que não podem ser utilizados.",
        "reset_done": (
            "A sua palavra-passe foi alterada. Inicie sessão na aplicação com a nova palavra-passe."
        ),
        "noscript": (
            "Esta página precisa de JavaScript para concluir. Ative-o e abra novamente a ligação."
        ),
        "missing_token": (
            "Esta ligação está incompleta. Abra-a novamente a partir do e-mail ou peça uma nova "
            "na aplicação."
        ),
        "invalid": "Esta ligação já não é válida. Peça uma nova na aplicação.",
        "expired": "Esta ligação expirou. Peça uma nova na aplicação.",
        "used": "Esta ligação já foi utilizada. Se foi o próprio, a alteração já está guardada.",
        "network": (
            "Não foi possível estabelecer ligação. Verifique a ligação à Internet e tente "
            "novamente."
        ),
        "rate_limited": "Demasiadas tentativas. Aguarde um momento e tente novamente.",
        "error": "Ocorreu um erro. Tente novamente dentro de momentos.",
        "working": "Aguarde…",
    },
    "ru": {
        "change_title": "Подтвердите новый адрес электронной почты",
        "change_intro": "Нажмите кнопку, чтобы заменить адрес электронной почты аккаунта {app} на тот, на который пришла эта ссылка. На всех устройствах будет выполнен выход.",
        "change_button": "Подтвердить новый адрес",
        "change_done": "Готово! Адрес электронной почты изменён. Войдите в приложение заново с новым адресом.",
        "change_unavailable": "Этот адрес больше нельзя использовать для этого аккаунта. Начните смену заново в приложении.",
        "verify_title": "Подтвердите адрес электронной почты",
        "verify_intro": (
            "Нажмите кнопку ниже, чтобы подтвердить, что это адрес электронной почты вашего "
            "аккаунта {app}."
        ),
        "verify_button": "Подтвердить адрес",
        "verify_done": (
            "Готово! Адрес электронной почты подтверждён. Можно вернуться в приложение."
        ),
        "reset_title": "Задайте новый пароль",
        "reset_intro": (
            "Придумайте новый пароль для аккаунта {app}. После сохранения вы выйдете из "
            "аккаунта на всех устройствах."
        ),
        "new_password": "Новый пароль",
        "confirm_password": "Повторите новый пароль",
        "password_hint": (
            "Не менее {min} символов. Подойдут несколько не связанных между собой слов."
        ),
        "show_password": "Показать пароли",
        "reset_button": "Сохранить новый пароль",
        "mismatch": "Пароли не совпадают.",
        "too_short": "Пароль должен содержать не менее {min} символов.",
        "too_long": "Пароль может содержать не более {max} символов.",
        "invalid_unicode": "Пароль содержит недопустимые символы.",
        "reset_done": "Пароль изменён. Войдите в приложение с новым паролем.",
        "noscript": (
            "Для завершения на этой странице нужен JavaScript. Включите его и снова откройте "
            "ссылку."
        ),
        "missing_token": (
            "Ссылка неполная. Откройте её ещё раз из письма или запросите новую в приложении."
        ),
        "invalid": "Эта ссылка больше не действует. Запросите новую в приложении.",
        "expired": "Срок действия ссылки истёк. Запросите новую в приложении.",
        "used": "Эта ссылка уже использована. Если это были вы, изменение уже сохранено.",
        "network": (
            "Не удалось подключиться. Проверьте подключение к интернету и повторите попытку."
        ),
        "rate_limited": "Слишком много попыток. Подождите немного и повторите попытку.",
        "error": "Что-то пошло не так. Повторите попытку чуть позже.",
        "working": "Подождите…",
    },
    "tr": {
        "change_title": "Yeni e-posta adresini onayla",
        "change_intro": "{app} hesabının e-posta adresini bu bağlantının gönderildiği adresle değiştirmek için düğmeye bas. Tüm cihazlardaki oturumların kapatılacak.",
        "change_button": "Yeni adresi onayla",
        "change_done": "Tamam! E-posta adresin değiştirildi. Uygulamada yeni adresinle yeniden giriş yap.",
        "change_unavailable": "Bu adres artık bu hesap için kullanılamaz. Değişikliği uygulamada yeniden başlat.",
        "verify_title": "E-posta adresini doğrula",
        "verify_intro": (
            "Bu adresin {app} hesabının e-posta adresi olduğunu doğrulamak için aşağıdaki "
            "düğmeye dokun."
        ),
        "verify_button": "Adresi doğrula",
        "verify_done": "Tamam! E-posta adresin doğrulandı. Artık uygulamaya dönebilirsin.",
        "reset_title": "Yeni şifre belirle",
        "reset_intro": (
            "{app} hesabın için yeni bir şifre seç. Kaydettikten sonra tüm cihazlarda oturumun "
            "kapatılır."
        ),
        "new_password": "Yeni şifre",
        "confirm_password": "Yeni şifreyi tekrarla",
        "password_hint": (
            "En az {min} karakter. Birbiriyle ilgisiz birkaç kelime iyi bir seçimdir."
        ),
        "show_password": "Şifreleri göster",
        "reset_button": "Yeni şifreyi kaydet",
        "mismatch": "Şifreler eşleşmiyor.",
        "too_short": "Şifre en az {min} karakter olmalıdır.",
        "too_long": "Şifre en fazla {max} karakter olabilir.",
        "invalid_unicode": "Şifre kullanılamayan karakterler içeriyor.",
        "reset_done": "Şifren değiştirildi. Uygulamada yeni şifrenle giriş yap.",
        "noscript": (
            "Bu sayfanın işlemi tamamlaması için JavaScript gerekir. Etkinleştir ve bağlantıyı "
            "yeniden aç."
        ),
        "missing_token": (
            "Bu bağlantı eksik. E-postadan yeniden aç veya uygulamadan yeni bir bağlantı iste."
        ),
        "invalid": "Bu bağlantı artık geçerli değil. Uygulamadan yeni bir bağlantı iste.",
        "expired": "Bu bağlantının süresi doldu. Uygulamadan yeni bir bağlantı iste.",
        "used": "Bu bağlantı zaten kullanıldı. Bunu sen yaptıysan değişiklik zaten kaydedildi.",
        "network": "Bağlantı kurulamadı. İnternet bağlantını kontrol et ve tekrar dene.",
        "rate_limited": "Çok fazla deneme. Biraz bekle ve tekrar dene.",
        "error": "Bir şeyler ters gitti. Birazdan tekrar dene.",
        "working": "Lütfen bekle…",
    },
    "vi": {
        "change_title": "Xác nhận địa chỉ email mới",
        "change_intro": "Nhấn nút bên dưới để đổi email của tài khoản {app} sang địa chỉ đã nhận liên kết này. Bạn sẽ bị đăng xuất khỏi mọi thiết bị.",
        "change_button": "Xác nhận địa chỉ mới",
        "change_done": "Xong! Địa chỉ email của bạn đã được đổi. Hãy đăng nhập lại vào ứng dụng bằng địa chỉ mới.",
        "change_unavailable": "Địa chỉ này không còn dùng được cho tài khoản này. Hãy bắt đầu đổi lại trong ứng dụng.",
        "verify_title": "Xác nhận địa chỉ email của bạn",
        "verify_intro": (
            "Nhấn nút bên dưới để xác nhận đây là địa chỉ email của tài khoản {app} của bạn."
        ),
        "verify_button": "Xác nhận địa chỉ",
        "verify_done": (
            "Xong! Địa chỉ email của bạn đã được xác nhận. Bạn có thể quay lại ứng dụng."
        ),
        "reset_title": "Đặt mật khẩu mới",
        "reset_intro": (
            "Chọn mật khẩu mới cho tài khoản {app} của bạn. Sau khi lưu, bạn sẽ bị đăng xuất "
            "trên tất cả thiết bị."
        ),
        "new_password": "Mật khẩu mới",
        "confirm_password": "Nhập lại mật khẩu mới",
        "password_hint": ("Ít nhất {min} ký tự. Vài từ không liên quan đến nhau là lựa chọn tốt."),
        "show_password": "Hiện mật khẩu",
        "reset_button": "Lưu mật khẩu mới",
        "mismatch": "Mật khẩu không khớp.",
        "too_short": "Mật khẩu phải có ít nhất {min} ký tự.",
        "too_long": "Mật khẩu chỉ được có tối đa {max} ký tự.",
        "invalid_unicode": "Mật khẩu chứa ký tự không thể sử dụng.",
        "reset_done": (
            "Mật khẩu của bạn đã được thay đổi. Hãy đăng nhập ứng dụng bằng mật khẩu mới."
        ),
        "noscript": (
            "Trang này cần JavaScript để hoàn tất. Hãy bật JavaScript và mở lại liên kết."
        ),
        "missing_token": (
            "Liên kết này không đầy đủ. Hãy mở lại từ email hoặc yêu cầu liên kết mới trong "
            "ứng dụng."
        ),
        "invalid": "Liên kết này không còn hợp lệ. Hãy yêu cầu liên kết mới trong ứng dụng.",
        "expired": "Liên kết này đã hết hạn. Hãy yêu cầu liên kết mới trong ứng dụng.",
        "used": "Liên kết này đã được sử dụng. Nếu đó là bạn, thay đổi đã được lưu.",
        "network": "Không thể kết nối. Hãy kiểm tra kết nối internet và thử lại.",
        "rate_limited": "Quá nhiều lần thử. Hãy đợi một lát rồi thử lại.",
        "error": "Đã xảy ra lỗi. Hãy thử lại sau giây lát.",
        "working": "Vui lòng đợi…",
    },
    "zh": {
        "change_title": "确认你的新邮箱地址",
        "change_intro": "点击下方按钮，将 {app} 账号的邮箱地址更改为收到此链接的地址。所有设备都将退出登录。",
        "change_button": "确认新地址",
        "change_done": "完成！你的邮箱地址已更改。请使用新地址重新登录应用。",
        "change_unavailable": "此地址已无法用于该账号。请在应用中重新发起更改。",
        "verify_title": "确认你的电子邮件地址",
        "verify_intro": "点击下方按钮，确认这是你的 {app} 账户所用的电子邮件地址。",
        "verify_button": "确认地址",
        "verify_done": "完成！你的电子邮件地址已确认，现在可以返回应用。",
        "reset_title": "设置新密码",
        "reset_intro": "为你的 {app} 账户设置新密码。保存后，你将在所有设备上退出登录。",
        "new_password": "新密码",
        "confirm_password": "再次输入新密码",
        "password_hint": "至少 {min} 个字符。几个互不相关的词语就是不错的选择。",
        "show_password": "显示密码",
        "reset_button": "保存新密码",
        "mismatch": "两次输入的密码不一致。",
        "too_short": "密码至少需要 {min} 个字符。",
        "too_long": "密码最多只能有 {max} 个字符。",
        "invalid_unicode": "密码包含无法使用的字符。",
        "reset_done": "密码已更改。请使用新密码登录应用。",
        "noscript": "此页面需要 JavaScript 才能完成操作。请启用后重新打开链接。",
        "missing_token": "此链接不完整。请从邮件中重新打开，或在应用中申请新的链接。",
        "invalid": "此链接已失效。请在应用中申请新的链接。",
        "expired": "此链接已过期。请在应用中申请新的链接。",
        "used": "此链接已被使用。如果是你本人操作，更改已经保存。",
        "network": "无法连接。请检查网络连接后重试。",
        "rate_limited": "尝试次数过多。请稍候再试。",
        "error": "出了点问题。请稍后重试。",
        "working": "请稍候…",
    },
    "ja": {
        "change_title": "新しいメールアドレスの確認",
        "change_intro": "下のボタンを押すと、{app} アカウントのメールアドレスがこのリンクの送信先に変更されます。すべての端末からログアウトされます。",
        "change_button": "新しいアドレスを確認",
        "change_done": "完了しました。メールアドレスが変更されました。新しいアドレスでアプリに再ログインしてください。",
        "change_unavailable": "このアドレスは、このアカウントではもう使えません。アプリで変更をやり直してください。",
        "verify_title": "メールアドレスの確認",
        "verify_intro": (
            "下のボタンを押して、{app} アカウントのメールアドレスであることを確認してください。"
        ),
        "verify_button": "アドレスを確認",
        "verify_done": "完了しました。メールアドレスが確認されました。アプリに戻ってください。",
        "reset_title": "新しいパスワードの設定",
        "reset_intro": (
            "{app} アカウントの新しいパスワードを決めてください。保存すると、すべての端末で"
            "ログアウトされます。"
        ),
        "new_password": "新しいパスワード",
        "confirm_password": "新しいパスワード（確認）",
        "password_hint": "{min} 文字以上。関連のない単語をいくつか並べるのがおすすめです。",
        "show_password": "パスワードを表示",
        "reset_button": "新しいパスワードを保存",
        "mismatch": "パスワードが一致しません。",
        "too_short": "パスワードは {min} 文字以上にしてください。",
        "too_long": "パスワードは {max} 文字以内にしてください。",
        "invalid_unicode": "パスワードに使用できない文字が含まれています。",
        "reset_done": "パスワードを変更しました。新しいパスワードでアプリにログインしてください。",
        "noscript": (
            "このページで操作を完了するには JavaScript が必要です。有効にしてから"
            "リンクを開き直してください。"
        ),
        "missing_token": (
            "このリンクは不完全です。メールから開き直すか、アプリで新しいリンクを"
            "リクエストしてください。"
        ),
        "invalid": (
            "このリンクは無効になっています。アプリで新しいリンクをリクエストしてください。"
        ),
        "expired": (
            "このリンクは有効期限が切れています。アプリで新しいリンクをリクエストしてください。"
        ),
        "used": ("このリンクはすでに使用されています。ご自身の操作であれば、変更は保存済みです。"),
        "network": ("接続できませんでした。インターネット接続を確認して、もう一度お試しください。"),
        "rate_limited": "試行回数が多すぎます。しばらく待ってからもう一度お試しください。",
        "error": "問題が発生しました。しばらくしてからもう一度お試しください。",
        "working": "お待ちください…",
    },
    "ko": {
        "change_title": "새 이메일 주소 확인",
        "change_intro": "아래 버튼을 누르면 {app} 계정의 이메일 주소가 이 링크를 받은 주소로 변경됩니다. 모든 기기에서 로그아웃됩니다.",
        "change_button": "새 주소 확인",
        "change_done": "완료되었습니다! 이메일 주소가 변경되었습니다. 새 주소로 앱에 다시 로그인하세요.",
        "change_unavailable": "이 주소는 더 이상 이 계정에 사용할 수 없습니다. 앱에서 변경을 다시 시작하세요.",
        "verify_title": "이메일 주소 확인",
        "verify_intro": "아래 버튼을 눌러 이 주소가 {app} 계정의 이메일 주소인지 확인해 주세요.",
        "verify_button": "주소 확인",
        "verify_done": "완료되었습니다! 이메일 주소가 확인되었습니다. 이제 앱으로 돌아가세요.",
        "reset_title": "새 비밀번호 설정",
        "reset_intro": (
            "{app} 계정의 새 비밀번호를 정해 주세요. 저장하면 모든 기기에서 로그아웃됩니다."
        ),
        "new_password": "새 비밀번호",
        "confirm_password": "새 비밀번호 다시 입력",
        "password_hint": "{min}자 이상. 서로 관련 없는 단어 몇 개를 이어 쓰면 좋습니다.",
        "show_password": "비밀번호 표시",
        "reset_button": "새 비밀번호 저장",
        "mismatch": "비밀번호가 일치하지 않습니다.",
        "too_short": "비밀번호는 {min}자 이상이어야 합니다.",
        "too_long": "비밀번호는 최대 {max}자까지 가능합니다.",
        "invalid_unicode": "비밀번호에 사용할 수 없는 문자가 포함되어 있습니다.",
        "reset_done": "비밀번호가 변경되었습니다. 새 비밀번호로 앱에 로그인해 주세요.",
        "noscript": (
            "이 페이지에서 작업을 완료하려면 JavaScript가 필요합니다. 켜고 링크를 다시 열어 주세요."
        ),
        "missing_token": (
            "링크가 완전하지 않습니다. 이메일에서 다시 열거나 앱에서 새 링크를 요청해 주세요."
        ),
        "invalid": "이 링크는 더 이상 유효하지 않습니다. 앱에서 새 링크를 요청해 주세요.",
        "expired": "이 링크는 만료되었습니다. 앱에서 새 링크를 요청해 주세요.",
        "used": (
            "이 링크는 이미 사용되었습니다. 본인이 사용했다면 변경 사항은 이미 저장되었습니다."
        ),
        "network": "연결할 수 없습니다. 인터넷 연결을 확인하고 다시 시도해 주세요.",
        "rate_limited": "시도 횟수가 너무 많습니다. 잠시 후 다시 시도해 주세요.",
        "error": "문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        "working": "잠시 기다려 주세요…",
    },
    "ar": {
        "change_title": "أكّد عنوان بريدك الإلكتروني الجديد",
        "change_intro": "اضغط على الزر أدناه لتغيير البريد الإلكتروني لحسابك في {app} إلى العنوان الذي وصله هذا الرابط. سيتم تسجيل خروجك من جميع الأجهزة.",
        "change_button": "تأكيد العنوان الجديد",
        "change_done": "تم! تغيّر عنوان بريدك الإلكتروني. سجّل الدخول إلى التطبيق من جديد بالعنوان الجديد.",
        "change_unavailable": "لم يعد بالإمكان استخدام هذا العنوان لهذا الحساب. ابدأ التغيير من جديد في التطبيق.",
        "verify_title": "أكِّد عنوان بريدك الإلكتروني",
        "verify_intro": (
            "اضغط على الزر أدناه لتأكيد أن هذا هو عنوان البريد الإلكتروني لحسابك في {app}."
        ),
        "verify_button": "تأكيد العنوان",
        "verify_done": "تم! تم تأكيد عنوان بريدك الإلكتروني. يمكنك العودة إلى التطبيق الآن.",
        "reset_title": "عيِّن كلمة مرور جديدة",
        "reset_intro": (
            "اختر كلمة مرور جديدة لحسابك في {app}. بعد الحفظ، سيتم تسجيل خروجك من جميع الأجهزة."
        ),
        "new_password": "كلمة المرور الجديدة",
        "confirm_password": "أعد إدخال كلمة المرور الجديدة",
        "password_hint": "{min} حرفًا على الأقل. بضع كلمات غير مترابطة خيار جيد.",
        "show_password": "إظهار كلمات المرور",
        "reset_button": "حفظ كلمة المرور الجديدة",
        "mismatch": "كلمتا المرور غير متطابقتين.",
        "too_short": "يجب أن تتكون كلمة المرور من {min} حرفًا على الأقل.",
        "too_long": "يمكن أن تتكون كلمة المرور من {max} حرفًا كحد أقصى.",
        "invalid_unicode": "تحتوي كلمة المرور على أحرف لا يمكن استخدامها.",
        "reset_done": (
            "تم تغيير كلمة المرور. سجِّل الدخول إلى التطبيق باستخدام كلمة المرور الجديدة."
        ),
        "noscript": (
            "تحتاج هذه الصفحة إلى JavaScript لإكمال العملية. فعِّله ثم افتح الرابط مرة أخرى."
        ),
        "missing_token": (
            "هذا الرابط غير مكتمل. افتحه مرة أخرى من البريد الإلكتروني أو اطلب رابطًا جديدًا "
            "من التطبيق."
        ),
        "invalid": "لم يعد هذا الرابط صالحًا. اطلب رابطًا جديدًا من التطبيق.",
        "expired": "انتهت صلاحية هذا الرابط. اطلب رابطًا جديدًا من التطبيق.",
        "used": "تم استخدام هذا الرابط بالفعل. إذا كنت أنت من استخدمه، فقد تم حفظ التغيير.",
        "network": "تعذَّر الاتصال. تحقَّق من اتصالك بالإنترنت ثم حاول مرة أخرى.",
        "rate_limited": "محاولات كثيرة جدًا. انتظر قليلًا ثم حاول مرة أخرى.",
        "error": "حدث خطأ ما. حاول مرة أخرى بعد قليل.",
        "working": "يرجى الانتظار…",
    },
    "hi": {
        "change_title": "अपना नया ईमेल पता पुष्टि करें",
        "change_intro": "अपने {app} खाते का ईमेल पता उस पते में बदलने के लिए नीचे का बटन दबाएँ जिस पर यह लिंक भेजा गया था। सभी डिवाइस से साइन आउट हो जाएगा।",
        "change_button": "नया पता पुष्टि करें",
        "change_done": "हो गया! आपका ईमेल पता बदल दिया गया है। नए पते से ऐप में फिर से साइन इन करें।",
        "change_unavailable": "यह पता अब इस खाते के लिए इस्तेमाल नहीं किया जा सकता। ऐप में बदलाव फिर से शुरू करें।",
        "verify_title": "अपने ईमेल पते की पुष्टि करें",
        "verify_intro": ("पुष्टि करने के लिए नीचे दिया गया बटन दबाएँ कि यह आपके {app} खाते का ईमेल पता है।"),
        "verify_button": "पते की पुष्टि करें",
        "verify_done": "हो गया! आपके ईमेल पते की पुष्टि हो गई है। अब आप ऐप पर लौट सकते हैं।",
        "reset_title": "नया पासवर्ड सेट करें",
        "reset_intro": (
            "अपने {app} खाते के लिए नया पासवर्ड चुनें। सेव करने के बाद आप सभी डिवाइस से साइन आउट हो जाएँगे।"
        ),
        "new_password": "नया पासवर्ड",
        "confirm_password": "नया पासवर्ड दोबारा लिखें",
        "password_hint": "कम से कम {min} वर्ण। कुछ आपस में असंबंधित शब्द अच्छा विकल्प हैं।",
        "show_password": "पासवर्ड दिखाएँ",
        "reset_button": "नया पासवर्ड सेव करें",
        "mismatch": "पासवर्ड मेल नहीं खाते।",
        "too_short": "पासवर्ड में कम से कम {min} वर्ण होने चाहिए।",
        "too_long": "पासवर्ड में अधिकतम {max} वर्ण हो सकते हैं।",
        "invalid_unicode": "पासवर्ड में ऐसे वर्ण हैं जिनका उपयोग नहीं किया जा सकता।",
        "reset_done": "आपका पासवर्ड बदल दिया गया है। नए पासवर्ड से ऐप में साइन इन करें।",
        "noscript": (
            "इस पेज को काम पूरा करने के लिए JavaScript की ज़रूरत है। इसे चालू करें और लिंक दोबारा खोलें।"
        ),
        "missing_token": ("यह लिंक अधूरा है। इसे ईमेल से दोबारा खोलें या ऐप में नए लिंक का अनुरोध करें।"),
        "invalid": "यह लिंक अब मान्य नहीं है। ऐप में नए लिंक का अनुरोध करें।",
        "expired": "इस लिंक की समय-सीमा समाप्त हो गई है। ऐप में नए लिंक का अनुरोध करें।",
        "used": ("इस लिंक का उपयोग पहले ही हो चुका है। अगर यह आपने किया था, तो बदलाव सेव हो चुका है।"),
        "network": "कनेक्ट नहीं हो सका। अपना इंटरनेट कनेक्शन जाँचें और फिर से कोशिश करें।",
        "rate_limited": "बहुत अधिक प्रयास। थोड़ी देर रुकें और फिर से कोशिश करें।",
        "error": "कुछ गलत हो गया। थोड़ी देर में फिर से कोशिश करें।",
        "working": "कृपया प्रतीक्षा करें…",
    },
}

for _locale, _texts in DELETION_TEXTS.items():
    PAGE_TEXTS[_locale].update(_texts)
    PAGE_TEXTS[_locale].update(
        dict(zip(BROWSER_KEYS, (*BROWSER_TEXTS[_locale], BROWSER_RECEIPT_TEXTS[_locale]), strict=True))
    )
KEYS = KEYS + DELETION_KEYS + BROWSER_KEYS
