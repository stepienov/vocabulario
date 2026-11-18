"""Account mail texts and rendering (E-001/F-004/T-002).

Locales mirror the Android UI catalog. Every locale must define every key; a test
enforces it. Rendering escapes all values for HTML and never puts a token anywhere
except the single link.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

APP_NAME = "Vocabulario"
DEFAULT_LOCALE = "en"
TEMPLATE_VERSION = "v1"
RTL_LOCALES = frozenset({"ar"})

KEYS = (
    "verify_subject",
    "verify_intro",
    "verify_action",
    "verify_expiry",
    "reset_subject",
    "reset_intro",
    "reset_action",
    "reset_expiry",
    "ignore",
    "link_hint",
    "changed_subject",
    "changed_body",
    "changed_help",
    "emailchange_subject",
    "emailchange_intro",
    "emailchange_action",
    "emailchange_expiry",
    "emailstart_subject",
    "emailstart_body",
    "emaildone_subject",
    "emaildone_body",
    "pwadded_subject",
    "pwadded_body",
)

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "pwadded_subject": "A password was added to your account",
        "pwadded_body": "A password was added to your {app} account. You can now sign in with it or with Google, and your other devices were signed out.",
        "emailchange_subject": "Confirm your new email address",
        "emailchange_intro": "Confirm that this will be the new email address of your {app} account. The address changes only after you open the link, and you will need to sign in again on every device.",
        "emailchange_action": "Confirm new address",
        "emailchange_expiry": "The link is valid for {hours} hours.",
        "emailstart_subject": "Change of your email address requested",
        "emailstart_body": "A change of the email address of your {app} account was requested. Nothing changes until the new address is confirmed.",
        "emaildone_subject": "Your email address was changed",
        "emaildone_body": "The email address of your {app} account was changed and all devices were signed out.",
        "verify_subject": "Confirm your email address",
        "verify_intro": "Confirm that this is the email address of your {app} account.",
        "verify_action": "Confirm email",
        "verify_expiry": "The link is valid for {hours} hours.",
        "reset_subject": "Reset your password",
        "reset_intro": "We received a request to reset the password of your {app} account.",
        "reset_action": "Set a new password",
        "reset_expiry": "The link is valid for {minutes} minutes and can be used once.",
        "ignore": "If you didn't request this, you can ignore this email.",
        "link_hint": "If the button doesn't work, open this link:",
        "changed_subject": "Your password was changed",
        "changed_body": (
            "The password of your {app} account was changed and devices using the old "
            "password were signed out."
        ),
        "changed_help": (
            "If this wasn't you, reset your password in the app right away and reply to this email."
        ),
    },
    "es": {
        "pwadded_subject": "Se ha añadido una contraseña a tu cuenta",
        "pwadded_body": "Se ha añadido una contraseña a tu cuenta de {app}. Ahora puedes iniciar sesión con ella o con Google, y se ha cerrado la sesión en tus otros dispositivos.",
        "emailchange_subject": "Confirma tu nueva dirección de correo",
        "emailchange_intro": "Confirma que esta será la nueva dirección de correo de tu cuenta de {app}. La dirección solo cambia cuando abras el enlace y tendrás que volver a iniciar sesión en todos tus dispositivos.",
        "emailchange_action": "Confirmar nueva dirección",
        "emailchange_expiry": "El enlace es válido durante {hours} horas.",
        "emailstart_subject": "Se ha solicitado cambiar tu dirección de correo",
        "emailstart_body": "Se ha solicitado cambiar la dirección de correo de tu cuenta de {app}. No cambia nada hasta que se confirme la nueva dirección.",
        "emaildone_subject": "Tu dirección de correo ha cambiado",
        "emaildone_body": "La dirección de correo de tu cuenta de {app} ha cambiado y se ha cerrado la sesión en todos los dispositivos.",
        "verify_subject": "Confirma tu dirección de correo",
        "verify_intro": "Confirma que esta es la dirección de correo de tu cuenta de {app}.",
        "verify_action": "Confirmar correo",
        "verify_expiry": "El enlace es válido durante {hours} horas.",
        "reset_subject": "Restablece tu contraseña",
        "reset_intro": (
            "Hemos recibido una solicitud para restablecer la contraseña de tu cuenta de {app}."
        ),
        "reset_action": "Crear una contraseña nueva",
        "reset_expiry": (
            "El enlace es válido durante {minutes} minutos y solo se puede usar una vez."
        ),
        "ignore": "Si no lo has solicitado tú, puedes ignorar este correo.",
        "link_hint": "Si el botón no funciona, abre este enlace:",
        "changed_subject": "Tu contraseña ha cambiado",
        "changed_body": (
            "La contraseña de tu cuenta de {app} ha cambiado y se ha cerrado la sesión en los "
            "dispositivos que usaban la anterior."
        ),
        "changed_help": (
            "Si no has sido tú, restablece la contraseña en la aplicación cuanto antes y "
            "responde a este correo."
        ),
    },
    "pl": {
        "pwadded_subject": "Do Twojego konta dodano hasło",
        "pwadded_body": "Do Twojego konta {app} dodano hasło. Możesz teraz logować się nim albo przez Google, a pozostałe urządzenia zostały wylogowane.",
        "emailchange_subject": "Potwierdź nowy adres e-mail",
        "emailchange_intro": "Potwierdź, że to będzie nowy adres e-mail Twojego konta {app}. Adres zmieni się dopiero po otwarciu linku, a na każdym urządzeniu trzeba będzie zalogować się ponownie.",
        "emailchange_action": "Potwierdź nowy adres",
        "emailchange_expiry": "Link jest ważny przez {hours} godz.",
        "emailstart_subject": "Poproszono o zmianę adresu e-mail",
        "emailstart_body": "Poproszono o zmianę adresu e-mail Twojego konta {app}. Nic się nie zmieni, dopóki nowy adres nie zostanie potwierdzony.",
        "emaildone_subject": "Adres e-mail został zmieniony",
        "emaildone_body": "Adres e-mail Twojego konta {app} został zmieniony, a wszystkie urządzenia zostały wylogowane.",
        "verify_subject": "Potwierdź swój adres e-mail",
        "verify_intro": "Potwierdź, że to adres e-mail Twojego konta w {app}.",
        "verify_action": "Potwierdź adres",
        "verify_expiry": "Link jest ważny przez {hours} godz.",
        "reset_subject": "Zresetuj hasło",
        "reset_intro": "Otrzymaliśmy prośbę o zresetowanie hasła do Twojego konta w {app}.",
        "reset_action": "Ustaw nowe hasło",
        "reset_expiry": "Link jest ważny przez {minutes} min i działa tylko raz.",
        "ignore": "Jeśli to nie Ty, zignoruj tę wiadomość.",
        "link_hint": "Jeśli przycisk nie działa, otwórz ten link:",
        "changed_subject": "Hasło zostało zmienione",
        "changed_body": (
            "Hasło do Twojego konta w {app} zostało zmienione, a urządzenia korzystające "
            "z poprzedniego hasła zostały wylogowane."
        ),
        "changed_help": (
            "Jeśli to nie Ty, jak najszybciej zresetuj hasło w aplikacji i odpowiedz na tę "
            "wiadomość."
        ),
    },
    "de": {
        "pwadded_subject": "Deinem Konto wurde ein Passwort hinzugefügt",
        "pwadded_body": "Deinem {app}-Konto wurde ein Passwort hinzugefügt. Du kannst dich jetzt damit oder mit Google anmelden, und deine anderen Geräte wurden abgemeldet.",
        "emailchange_subject": "Bestätige deine neue E-Mail-Adresse",
        "emailchange_intro": "Bestätige, dass dies die neue E-Mail-Adresse deines {app}-Kontos wird. Die Adresse ändert sich erst, wenn du den Link öffnest, und du musst dich auf jedem Gerät neu anmelden.",
        "emailchange_action": "Neue Adresse bestätigen",
        "emailchange_expiry": "Der Link ist {hours} Stunden gültig.",
        "emailstart_subject": "Änderung deiner E-Mail-Adresse angefordert",
        "emailstart_body": "Für dein {app}-Konto wurde eine Änderung der E-Mail-Adresse angefordert. Es ändert sich nichts, bis die neue Adresse bestätigt ist.",
        "emaildone_subject": "Deine E-Mail-Adresse wurde geändert",
        "emaildone_body": "Die E-Mail-Adresse deines {app}-Kontos wurde geändert und alle Geräte wurden abgemeldet.",
        "verify_subject": "Bestätige deine E-Mail-Adresse",
        "verify_intro": "Bestätige, dass dies die E-Mail-Adresse deines {app}-Kontos ist.",
        "verify_action": "E-Mail bestätigen",
        "verify_expiry": "Der Link ist {hours} Stunden gültig.",
        "reset_subject": "Setze dein Passwort zurück",
        "reset_intro": (
            "Wir haben eine Anfrage erhalten, das Passwort deines {app}-Kontos zurückzusetzen."
        ),
        "reset_action": "Neues Passwort festlegen",
        "reset_expiry": (
            "Der Link ist {minutes} Minuten gültig und kann nur einmal verwendet werden."
        ),
        "ignore": "Wenn du das nicht angefordert hast, kannst du diese E-Mail ignorieren.",
        "link_hint": "Falls die Schaltfläche nicht funktioniert, öffne diesen Link:",
        "changed_subject": "Dein Passwort wurde geändert",
        "changed_body": (
            "Das Passwort deines {app}-Kontos wurde geändert. Geräte, die das alte Passwort "
            "verwendet haben, wurden abgemeldet."
        ),
        "changed_help": (
            "Wenn du das nicht warst, setze dein Passwort sofort in der App zurück und "
            "antworte auf diese E-Mail."
        ),
    },
    "fr": {
        "pwadded_subject": "Un mot de passe a été ajouté à votre compte",
        "pwadded_body": "Un mot de passe a été ajouté à votre compte {app}. Vous pouvez désormais vous connecter avec lui ou avec Google, et vos autres appareils ont été déconnectés.",
        "emailchange_subject": "Confirmez votre nouvelle adresse e-mail",
        "emailchange_intro": "Confirmez que ce sera la nouvelle adresse e-mail de votre compte {app}. L'adresse ne change qu'après l'ouverture du lien et vous devrez vous reconnecter sur chaque appareil.",
        "emailchange_action": "Confirmer la nouvelle adresse",
        "emailchange_expiry": "Le lien est valable {hours} heures.",
        "emailstart_subject": "Changement de votre adresse e-mail demandé",
        "emailstart_body": "Un changement de l'adresse e-mail de votre compte {app} a été demandé. Rien ne change tant que la nouvelle adresse n'est pas confirmée.",
        "emaildone_subject": "Votre adresse e-mail a été modifiée",
        "emaildone_body": "L'adresse e-mail de votre compte {app} a été modifiée et tous les appareils ont été déconnectés.",
        "verify_subject": "Confirmez votre adresse e-mail",
        "verify_intro": ("Confirmez qu'il s'agit bien de l'adresse e-mail de votre compte {app}."),
        "verify_action": "Confirmer l'adresse",
        "verify_expiry": "Le lien est valable {hours} heures.",
        "reset_subject": "Réinitialisez votre mot de passe",
        "reset_intro": (
            "Nous avons reçu une demande de réinitialisation du mot de passe de votre compte {app}."
        ),
        "reset_action": "Choisir un nouveau mot de passe",
        "reset_expiry": (
            "Le lien est valable {minutes} minutes et ne peut être utilisé qu'une seule fois."
        ),
        "ignore": (
            "Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet e-mail."
        ),
        "link_hint": "Si le bouton ne fonctionne pas, ouvrez ce lien :",
        "changed_subject": "Votre mot de passe a été modifié",
        "changed_body": (
            "Le mot de passe de votre compte {app} a été modifié et les appareils qui "
            "utilisaient l'ancien ont été déconnectés."
        ),
        "changed_help": (
            "Si ce n'est pas vous, réinitialisez immédiatement votre mot de passe dans "
            "l'application et répondez à cet e-mail."
        ),
    },
    "it": {
        "pwadded_subject": "È stata aggiunta una password al tuo account",
        "pwadded_body": "È stata aggiunta una password al tuo account {app}. Ora puoi accedere con essa o con Google e gli altri dispositivi sono stati disconnessi.",
        "emailchange_subject": "Conferma il tuo nuovo indirizzo e-mail",
        "emailchange_intro": "Conferma che questo sarà il nuovo indirizzo e-mail del tuo account {app}. L'indirizzo cambia solo dopo aver aperto il link e dovrai accedere di nuovo su ogni dispositivo.",
        "emailchange_action": "Conferma il nuovo indirizzo",
        "emailchange_expiry": "Il link è valido per {hours} ore.",
        "emailstart_subject": "Richiesta di modifica del tuo indirizzo e-mail",
        "emailstart_body": "È stata richiesta la modifica dell'indirizzo e-mail del tuo account {app}. Non cambia nulla finché il nuovo indirizzo non viene confermato.",
        "emaildone_subject": "Il tuo indirizzo e-mail è stato modificato",
        "emaildone_body": "L'indirizzo e-mail del tuo account {app} è stato modificato e tutti i dispositivi sono stati disconnessi.",
        "verify_subject": "Conferma il tuo indirizzo email",
        "verify_intro": "Conferma che questo è l'indirizzo email del tuo account {app}.",
        "verify_action": "Conferma email",
        "verify_expiry": "Il link è valido per {hours} ore.",
        "reset_subject": "Reimposta la password",
        "reset_intro": (
            "Abbiamo ricevuto una richiesta di reimpostazione della password del tuo account {app}."
        ),
        "reset_action": "Imposta una nuova password",
        "reset_expiry": (
            "Il link è valido per {minutes} minuti e può essere usato una sola volta."
        ),
        "ignore": "Se non hai fatto tu questa richiesta, puoi ignorare questa email.",
        "link_hint": "Se il pulsante non funziona, apri questo link:",
        "changed_subject": "La tua password è stata modificata",
        "changed_body": (
            "La password del tuo account {app} è stata modificata e i dispositivi che usavano "
            "quella precedente sono stati disconnessi."
        ),
        "changed_help": (
            "Se non sei stato tu, reimposta subito la password nell'app e rispondi a questa email."
        ),
    },
    "pt-BR": {
        "pwadded_subject": "Uma senha foi adicionada à sua conta",
        "pwadded_body": "Uma senha foi adicionada à sua conta {app}. Agora você pode entrar com ela ou com o Google, e seus outros dispositivos foram desconectados.",
        "emailchange_subject": "Confirme seu novo endereço de e-mail",
        "emailchange_intro": "Confirme que este será o novo endereço de e-mail da sua conta {app}. O endereço só muda depois que você abrir o link e será preciso entrar de novo em todos os dispositivos.",
        "emailchange_action": "Confirmar novo endereço",
        "emailchange_expiry": "O link é válido por {hours} horas.",
        "emailstart_subject": "Mudança do seu endereço de e-mail solicitada",
        "emailstart_body": "Foi solicitada a mudança do endereço de e-mail da sua conta {app}. Nada muda até que o novo endereço seja confirmado.",
        "emaildone_subject": "Seu endereço de e-mail foi alterado",
        "emaildone_body": "O endereço de e-mail da sua conta {app} foi alterado e todos os dispositivos foram desconectados.",
        "verify_subject": "Confirme seu endereço de e-mail",
        "verify_intro": "Confirme que este é o e-mail da sua conta do {app}.",
        "verify_action": "Confirmar e-mail",
        "verify_expiry": "O link é válido por {hours} horas.",
        "reset_subject": "Redefina sua senha",
        "reset_intro": "Recebemos uma solicitação para redefinir a senha da sua conta do {app}.",
        "reset_action": "Criar nova senha",
        "reset_expiry": "O link é válido por {minutes} minutos e só pode ser usado uma vez.",
        "ignore": "Se não foi você que pediu, pode ignorar este e-mail.",
        "link_hint": "Se o botão não funcionar, abra este link:",
        "changed_subject": "Sua senha foi alterada",
        "changed_body": (
            "A senha da sua conta do {app} foi alterada e os dispositivos que usavam a senha "
            "anterior foram desconectados."
        ),
        "changed_help": (
            "Se não foi você, redefina sua senha no app imediatamente e responda a este e-mail."
        ),
    },
    "pt-PT": {
        "pwadded_subject": "Foi adicionada uma palavra-passe à sua conta",
        "pwadded_body": "Foi adicionada uma palavra-passe à sua conta {app}. Agora pode iniciar sessão com ela ou com o Google, e os seus outros dispositivos foram desligados.",
        "emailchange_subject": "Confirme o seu novo endereço de e-mail",
        "emailchange_intro": "Confirme que este será o novo endereço de e-mail da sua conta {app}. O endereço só muda depois de abrir a ligação e terá de iniciar sessão de novo em todos os dispositivos.",
        "emailchange_action": "Confirmar novo endereço",
        "emailchange_expiry": "A ligação é válida durante {hours} horas.",
        "emailstart_subject": "Alteração do seu endereço de e-mail pedida",
        "emailstart_body": "Foi pedida a alteração do endereço de e-mail da sua conta {app}. Nada muda até o novo endereço ser confirmado.",
        "emaildone_subject": "O seu endereço de e-mail foi alterado",
        "emaildone_body": "O endereço de e-mail da sua conta {app} foi alterado e todos os dispositivos foram desligados.",
        "verify_subject": "Confirme o seu endereço de e-mail",
        "verify_intro": "Confirme que este é o e-mail da sua conta {app}.",
        "verify_action": "Confirmar e-mail",
        "verify_expiry": "A ligação é válida durante {hours} horas.",
        "reset_subject": "Reponha a sua palavra-passe",
        "reset_intro": "Recebemos um pedido para repor a palavra-passe da sua conta {app}.",
        "reset_action": "Definir nova palavra-passe",
        "reset_expiry": (
            "A ligação é válida durante {minutes} minutos e só pode ser utilizada uma vez."
        ),
        "ignore": "Se não fez este pedido, pode ignorar este e-mail.",
        "link_hint": "Se o botão não funcionar, abra esta ligação:",
        "changed_subject": "A sua palavra-passe foi alterada",
        "changed_body": (
            "A palavra-passe da sua conta {app} foi alterada e os dispositivos que usavam a "
            "anterior terminaram a sessão."
        ),
        "changed_help": (
            "Se não reconhece esta alteração, reponha de imediato a palavra-passe na "
            "aplicação e responda a este e-mail."
        ),
    },
    "ru": {
        "pwadded_subject": "К вашему аккаунту добавлен пароль",
        "pwadded_body": "К вашему аккаунту {app} добавлен пароль. Теперь вы можете входить с ним или через Google, а на других устройствах выполнен выход.",
        "emailchange_subject": "Подтвердите новый адрес электронной почты",
        "emailchange_intro": "Подтвердите, что это будет новый адрес электронной почты вашего аккаунта {app}. Адрес изменится только после перехода по ссылке, и на каждом устройстве придётся войти заново.",
        "emailchange_action": "Подтвердить новый адрес",
        "emailchange_expiry": "Ссылка действует {hours} ч.",
        "emailstart_subject": "Запрошена смена адреса электронной почты",
        "emailstart_body": "Запрошена смена адреса электронной почты вашего аккаунта {app}. Пока новый адрес не подтверждён, ничего не изменится.",
        "emaildone_subject": "Адрес электронной почты изменён",
        "emaildone_body": "Адрес электронной почты вашего аккаунта {app} изменён, на всех устройствах выполнен выход.",
        "verify_subject": "Подтвердите адрес электронной почты",
        "verify_intro": ("Подтвердите, что это адрес электронной почты вашего аккаунта {app}."),
        "verify_action": "Подтвердить адрес",
        "verify_expiry": "Ссылка действительна {hours} ч.",
        "reset_subject": "Сброс пароля",
        "reset_intro": "Мы получили запрос на сброс пароля для вашего аккаунта {app}.",
        "reset_action": "Задать новый пароль",
        "reset_expiry": (
            "Ссылка действительна {minutes} мин. и может быть использована только один раз."
        ),
        "ignore": "Если вы не отправляли этот запрос, просто проигнорируйте это письмо.",
        "link_hint": "Если кнопка не работает, откройте эту ссылку:",
        "changed_subject": "Ваш пароль изменён",
        "changed_body": (
            "Пароль вашего аккаунта {app} был изменён, а на устройствах со старым паролем "
            "выполнен выход."
        ),
        "changed_help": (
            "Если это были не вы, срочно сбросьте пароль в приложении и ответьте на это письмо."
        ),
    },
    "tr": {
        "pwadded_subject": "Hesabına bir parola eklendi",
        "pwadded_body": "{app} hesabına bir parola eklendi. Artık bununla ya da Google ile giriş yapabilirsin; diğer cihazlardaki oturumlar kapatıldı.",
        "emailchange_subject": "Yeni e-posta adresini onayla",
        "emailchange_intro": "Bunun {app} hesabının yeni e-posta adresi olacağını onayla. Adres yalnızca bağlantıyı açtıktan sonra değişir ve her cihazda yeniden giriş yapman gerekir.",
        "emailchange_action": "Yeni adresi onayla",
        "emailchange_expiry": "Bağlantı {hours} saat geçerlidir.",
        "emailstart_subject": "E-posta adresi değişikliği istendi",
        "emailstart_body": "{app} hesabının e-posta adresinin değiştirilmesi istendi. Yeni adres onaylanana kadar hiçbir şey değişmez.",
        "emaildone_subject": "E-posta adresin değiştirildi",
        "emaildone_body": "{app} hesabının e-posta adresi değiştirildi ve tüm cihazlardaki oturumlar kapatıldı.",
        "verify_subject": "E-posta adresini doğrula",
        "verify_intro": "Bu adresin {app} hesabının e-posta adresi olduğunu doğrula.",
        "verify_action": "E-postayı doğrula",
        "verify_expiry": "Bağlantı {hours} saat geçerlidir.",
        "reset_subject": "Şifreni sıfırla",
        "reset_intro": "{app} hesabının şifresini sıfırlama isteği aldık.",
        "reset_action": "Yeni şifre belirle",
        "reset_expiry": (
            "Bağlantı {minutes} dakika geçerlidir ve yalnızca bir kez kullanılabilir."
        ),
        "ignore": "Bu isteği sen yapmadıysan bu e-postayı yok sayabilirsin.",
        "link_hint": "Düğme çalışmazsa bu bağlantıyı aç:",
        "changed_subject": "Şifren değiştirildi",
        "changed_body": (
            "{app} hesabının şifresi değiştirildi ve eski şifreyi kullanan cihazlarda oturum "
            "kapatıldı."
        ),
        "changed_help": (
            "Bunu sen yapmadıysan şifreni uygulamada hemen sıfırla ve bu e-postayı yanıtla."
        ),
    },
    "vi": {
        "pwadded_subject": "Đã thêm mật khẩu vào tài khoản của bạn",
        "pwadded_body": "Đã thêm một mật khẩu vào tài khoản {app} của bạn. Giờ bạn có thể đăng nhập bằng mật khẩu hoặc Google, và các thiết bị khác đã bị đăng xuất.",
        "emailchange_subject": "Xác nhận địa chỉ email mới",
        "emailchange_intro": "Hãy xác nhận đây sẽ là địa chỉ email mới của tài khoản {app}. Địa chỉ chỉ đổi sau khi bạn mở liên kết và bạn sẽ phải đăng nhập lại trên mọi thiết bị.",
        "emailchange_action": "Xác nhận địa chỉ mới",
        "emailchange_expiry": "Liên kết có hiệu lực trong {hours} giờ.",
        "emailstart_subject": "Đã có yêu cầu đổi địa chỉ email",
        "emailstart_body": "Đã có yêu cầu đổi địa chỉ email của tài khoản {app}. Sẽ không có gì thay đổi cho đến khi địa chỉ mới được xác nhận.",
        "emaildone_subject": "Địa chỉ email của bạn đã được đổi",
        "emaildone_body": "Địa chỉ email của tài khoản {app} đã được đổi và mọi thiết bị đã bị đăng xuất.",
        "verify_subject": "Xác nhận địa chỉ email của bạn",
        "verify_intro": "Hãy xác nhận đây là địa chỉ email của tài khoản {app} của bạn.",
        "verify_action": "Xác nhận email",
        "verify_expiry": "Liên kết có hiệu lực trong {hours} giờ.",
        "reset_subject": "Đặt lại mật khẩu",
        "reset_intro": (
            "Chúng tôi đã nhận được yêu cầu đặt lại mật khẩu cho tài khoản {app} của bạn."
        ),
        "reset_action": "Đặt mật khẩu mới",
        "reset_expiry": "Liên kết có hiệu lực trong {minutes} phút và chỉ dùng được một lần.",
        "ignore": "Nếu bạn không yêu cầu, hãy bỏ qua email này.",
        "link_hint": "Nếu nút không hoạt động, hãy mở liên kết này:",
        "changed_subject": "Mật khẩu của bạn đã được thay đổi",
        "changed_body": (
            "Mật khẩu tài khoản {app} của bạn đã được thay đổi và các thiết bị dùng mật khẩu "
            "cũ đã bị đăng xuất."
        ),
        "changed_help": (
            "Nếu không phải bạn, hãy đặt lại mật khẩu trong ứng dụng ngay và trả lời email này."
        ),
    },
    "zh": {
        "pwadded_subject": "你的账号已添加密码",
        "pwadded_body": "你的 {app} 账号已添加密码。现在可以使用密码或 Google 登录，其他设备已退出登录。",
        "emailchange_subject": "确认你的新邮箱地址",
        "emailchange_intro": "请确认这将成为你的 {app} 账号的新邮箱地址。只有打开链接后地址才会更改，并且所有设备都需要重新登录。",
        "emailchange_action": "确认新地址",
        "emailchange_expiry": "链接有效期为 {hours} 小时。",
        "emailstart_subject": "已请求更改你的邮箱地址",
        "emailstart_body": "有人请求更改你的 {app} 账号的邮箱地址。在新地址确认之前不会有任何变化。",
        "emaildone_subject": "你的邮箱地址已更改",
        "emaildone_body": "你的 {app} 账号的邮箱地址已更改，所有设备均已退出登录。",
        "verify_subject": "请确认你的电子邮件地址",
        "verify_intro": "请确认这是你的 {app} 账户所用的电子邮件地址。",
        "verify_action": "确认邮箱",
        "verify_expiry": "链接在 {hours} 小时内有效。",
        "reset_subject": "重置密码",
        "reset_intro": "我们收到了重置你的 {app} 账户密码的请求。",
        "reset_action": "设置新密码",
        "reset_expiry": "链接在 {minutes} 分钟内有效，且只能使用一次。",
        "ignore": "如果这不是你本人的操作，请忽略此邮件。",
        "link_hint": "如果按钮无法使用，请打开此链接：",
        "changed_subject": "你的密码已更改",
        "changed_body": "你的 {app} 账户密码已更改，使用旧密码的设备已退出登录。",
        "changed_help": "如果这不是你本人的操作，请立即在应用中重置密码并回复此邮件。",
    },
    "ja": {
        "pwadded_subject": "アカウントにパスワードが追加されました",
        "pwadded_body": "{app} アカウントにパスワードが追加されました。今後はパスワードまたは Google でログインでき、他の端末はログアウトされました。",
        "emailchange_subject": "新しいメールアドレスの確認",
        "emailchange_intro": "これが {app} アカウントの新しいメールアドレスであることを確認してください。リンクを開くまでアドレスは変わらず、すべての端末で再ログインが必要になります。",
        "emailchange_action": "新しいアドレスを確認",
        "emailchange_expiry": "リンクの有効期限は {hours} 時間です。",
        "emailstart_subject": "メールアドレスの変更がリクエストされました",
        "emailstart_body": "{app} アカウントのメールアドレスの変更がリクエストされました。新しいアドレスが確認されるまで何も変わりません。",
        "emaildone_subject": "メールアドレスが変更されました",
        "emaildone_body": "{app} アカウントのメールアドレスが変更され、すべての端末がログアウトされました。",
        "verify_subject": "メールアドレスの確認",
        "verify_intro": "{app} アカウントのメールアドレスであることを確認してください。",
        "verify_action": "メールアドレスを確認",
        "verify_expiry": "リンクの有効期限は {hours} 時間です。",
        "reset_subject": "パスワードの再設定",
        "reset_intro": "{app} アカウントのパスワード再設定のリクエストを受け付けました。",
        "reset_action": "新しいパスワードを設定",
        "reset_expiry": "リンクの有効期限は {minutes} 分で、1 回のみ使用できます。",
        "ignore": "心当たりがない場合は、このメールを無視してください。",
        "link_hint": "ボタンが機能しない場合は、次のリンクを開いてください：",
        "changed_subject": "パスワードが変更されました",
        "changed_body": (
            "{app} アカウントのパスワードが変更され、以前のパスワードを使用していた端末は"
            "ログアウトされました。"
        ),
        "changed_help": (
            "心当たりがない場合は、すぐにアプリでパスワードを再設定し、このメールに"
            "返信してください。"
        ),
    },
    "ko": {
        "pwadded_subject": "계정에 비밀번호가 추가되었습니다",
        "pwadded_body": "{app} 계정에 비밀번호가 추가되었습니다. 이제 비밀번호 또는 Google로 로그인할 수 있으며, 다른 기기는 로그아웃되었습니다.",
        "emailchange_subject": "새 이메일 주소 확인",
        "emailchange_intro": "이 주소가 {app} 계정의 새 이메일 주소가 맞는지 확인해 주세요. 링크를 열어야 주소가 바뀌며, 모든 기기에서 다시 로그인해야 합니다.",
        "emailchange_action": "새 주소 확인",
        "emailchange_expiry": "링크는 {hours}시간 동안 유효합니다.",
        "emailstart_subject": "이메일 주소 변경이 요청되었습니다",
        "emailstart_body": "{app} 계정의 이메일 주소 변경이 요청되었습니다. 새 주소를 확인하기 전까지는 아무것도 바뀌지 않습니다.",
        "emaildone_subject": "이메일 주소가 변경되었습니다",
        "emaildone_body": "{app} 계정의 이메일 주소가 변경되었고 모든 기기에서 로그아웃되었습니다.",
        "verify_subject": "이메일 주소를 확인해 주세요",
        "verify_intro": "이 주소가 {app} 계정의 이메일 주소인지 확인해 주세요.",
        "verify_action": "이메일 확인",
        "verify_expiry": "링크는 {hours}시간 동안 유효합니다.",
        "reset_subject": "비밀번호 재설정",
        "reset_intro": "{app} 계정의 비밀번호 재설정 요청을 받았습니다.",
        "reset_action": "새 비밀번호 설정",
        "reset_expiry": "링크는 {minutes}분 동안 유효하며 한 번만 사용할 수 있습니다.",
        "ignore": "요청하지 않으셨다면 이 이메일을 무시하셔도 됩니다.",
        "link_hint": "버튼이 작동하지 않으면 다음 링크를 여세요:",
        "changed_subject": "비밀번호가 변경되었습니다",
        "changed_body": (
            "{app} 계정의 비밀번호가 변경되었으며, 이전 비밀번호를 사용하던 기기에서는 "
            "로그아웃되었습니다."
        ),
        "changed_help": (
            "본인이 변경하지 않았다면 즉시 앱에서 비밀번호를 재설정하고 이 이메일에 회신해 주세요."
        ),
    },
    "ar": {
        "pwadded_subject": "تمت إضافة كلمة مرور إلى حسابك",
        "pwadded_body": "تمت إضافة كلمة مرور إلى حسابك في {app}. يمكنك الآن تسجيل الدخول بها أو عبر Google، وتم تسجيل الخروج من أجهزتك الأخرى.",
        "emailchange_subject": "أكّد عنوان بريدك الإلكتروني الجديد",
        "emailchange_intro": "أكّد أن هذا سيكون عنوان البريد الإلكتروني الجديد لحسابك في {app}. لن يتغير العنوان إلا بعد فتح الرابط، وستحتاج إلى تسجيل الدخول من جديد على كل جهاز.",
        "emailchange_action": "تأكيد العنوان الجديد",
        "emailchange_expiry": "الرابط صالح لمدة {hours} ساعة.",
        "emailstart_subject": "طُلب تغيير عنوان بريدك الإلكتروني",
        "emailstart_body": "طُلب تغيير عنوان البريد الإلكتروني لحسابك في {app}. لن يتغير أي شيء حتى يتم تأكيد العنوان الجديد.",
        "emaildone_subject": "تم تغيير عنوان بريدك الإلكتروني",
        "emaildone_body": "تم تغيير عنوان البريد الإلكتروني لحسابك في {app} وتسجيل الخروج من جميع الأجهزة.",
        "verify_subject": "أكِّد عنوان بريدك الإلكتروني",
        "verify_intro": "أكِّد أن هذا هو عنوان البريد الإلكتروني لحسابك في {app}.",
        "verify_action": "تأكيد البريد الإلكتروني",
        "verify_expiry": "الرابط صالح لمدة {hours} ساعة.",
        "reset_subject": "إعادة تعيين كلمة المرور",
        "reset_intro": "تلقينا طلبًا لإعادة تعيين كلمة المرور لحسابك في {app}.",
        "reset_action": "تعيين كلمة مرور جديدة",
        "reset_expiry": "الرابط صالح لمدة {minutes} دقيقة ويمكن استخدامه مرة واحدة فقط.",
        "ignore": "إذا لم تطلب ذلك، يمكنك تجاهل هذه الرسالة.",
        "link_hint": "إذا لم يعمل الزر، فافتح هذا الرابط:",
        "changed_subject": "تم تغيير كلمة المرور",
        "changed_body": (
            "تم تغيير كلمة المرور لحسابك في {app}، وتم تسجيل الخروج من الأجهزة التي كانت "
            "تستخدم كلمة المرور السابقة."
        ),
        "changed_help": (
            "إذا لم تكن أنت من قام بذلك، فأعد تعيين كلمة المرور في التطبيق فورًا وردّ على "
            "هذه الرسالة."
        ),
    },
    "hi": {
        "pwadded_subject": "आपके खाते में पासवर्ड जोड़ा गया",
        "pwadded_body": "आपके {app} खाते में पासवर्ड जोड़ा गया। अब आप उससे या Google से साइन इन कर सकते हैं, और आपके अन्य डिवाइस साइन आउट कर दिए गए हैं।",
        "emailchange_subject": "अपना नया ईमेल पता पुष्टि करें",
        "emailchange_intro": "पुष्टि करें कि यह आपके {app} खाते का नया ईमेल पता होगा। पता तभी बदलेगा जब आप लिंक खोलेंगे, और हर डिवाइस पर आपको फिर से साइन इन करना होगा।",
        "emailchange_action": "नया पता पुष्टि करें",
        "emailchange_expiry": "लिंक {hours} घंटे के लिए मान्य है।",
        "emailstart_subject": "आपका ईमेल पता बदलने का अनुरोध किया गया",
        "emailstart_body": "आपके {app} खाते का ईमेल पता बदलने का अनुरोध किया गया। नए पते की पुष्टि होने तक कुछ नहीं बदलेगा।",
        "emaildone_subject": "आपका ईमेल पता बदल दिया गया है",
        "emaildone_body": "आपके {app} खाते का ईमेल पता बदल दिया गया है और सभी डिवाइस से साइन आउट कर दिया गया है।",
        "verify_subject": "अपने ईमेल पते की पुष्टि करें",
        "verify_intro": "पुष्टि करें कि यह आपके {app} खाते का ईमेल पता है।",
        "verify_action": "ईमेल की पुष्टि करें",
        "verify_expiry": "लिंक {hours} घंटे तक मान्य है।",
        "reset_subject": "अपना पासवर्ड रीसेट करें",
        "reset_intro": "हमें आपके {app} खाते का पासवर्ड रीसेट करने का अनुरोध मिला है।",
        "reset_action": "नया पासवर्ड सेट करें",
        "reset_expiry": ("लिंक {minutes} मिनट तक मान्य है और केवल एक बार इस्तेमाल किया जा सकता है।"),
        "ignore": "अगर आपने यह अनुरोध नहीं किया है, तो इस ईमेल को अनदेखा करें।",
        "link_hint": "अगर बटन काम नहीं करता, तो यह लिंक खोलें:",
        "changed_subject": "आपका पासवर्ड बदल दिया गया है",
        "changed_body": (
            "आपके {app} खाते का पासवर्ड बदल दिया गया है और पुराने पासवर्ड का इस्तेमाल करने "
            "वाले डिवाइस से साइन आउट कर दिया गया है।"
        ),
        "changed_help": (
            "अगर यह आपने नहीं किया, तो तुरंत ऐप में अपना पासवर्ड रीसेट करें और इस ईमेल का जवाब दें।"
        ),
    },
}

SUPPORTED_LOCALES = frozenset(TEXTS)
# A bare language picks the variant most testers use; regional ones fall back to the base.
_LANGUAGE_DEFAULTS = {"pt": "pt-BR"}


@dataclass(frozen=True)
class RenderedMail:
    subject: str
    text: str
    html: str
    locale: str
    template: str


def normalize_locale(value: str | None) -> str:
    """Map an app/UI language tag (e.g. `pt-rBR`, `pt_BR`, `de-AT`) to a supported locale."""
    raw = (value or "").strip().replace("_", "-")
    if not raw or len(raw) > 16:
        return DEFAULT_LOCALE
    parts = [p for p in raw.split("-") if p]
    if not parts:
        return DEFAULT_LOCALE
    language = parts[0].lower()
    if len(parts) > 1:
        region = parts[1]
        if len(region) == 3 and region[0] in "rR":
            region = region[1:]
        candidate = f"{language}-{region.upper()}"
        if candidate in SUPPORTED_LOCALES:
            return candidate
    if language in SUPPORTED_LOCALES:
        return language
    return _LANGUAGE_DEFAULTS.get(language, DEFAULT_LOCALE)


def _texts(locale: str) -> dict[str, str]:
    return TEXTS[normalize_locale(locale)]


def _fmt(texts: dict[str, str], key: str, **values: object) -> str:
    return texts[key].format(app=APP_NAME, **values)


def _html(
    locale: str,
    paragraphs: list[str],
    link: str | None,
    action: str | None,
    hint: str | None,
    after: list[str],
) -> str:
    direction = "rtl" if locale in RTL_LOCALES else "ltr"
    parts = [
        (
            f'<!doctype html><html lang="{escape(locale)}" dir="{direction}"><body '
            'style="font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.5;'
            'color:#1f2328;margin:0;padding:24px">'
        )
    ]
    parts += [f"<p>{escape(p)}</p>" for p in paragraphs]
    if link is not None and action is not None and hint is not None:
        href = escape(link, quote=True)
        parts.append(
            f'<p><a href="{href}" style="display:inline-block;padding:12px 20px;'
            'background:#1a73e8;color:#ffffff;text-decoration:none;border-radius:6px">'
            f"{escape(action)}</a></p>"
        )
        parts.append(
            f'<p style="font-size:14px">{escape(hint)}<br><a href="{href}">{escape(link)}</a></p>'
        )
    parts += [f'<p style="font-size:14px;color:#57606a">{escape(p)}</p>' for p in after]
    parts.append(f'<p style="font-size:14px;color:#57606a">{escape(APP_NAME)}</p></body></html>')
    return "".join(parts)


_LINK_PREFIX = {"verify_email": "verify", "reset_password": "reset", "change_email": "emailchange"}


def _link_mail(kind: str, locale: str, link: str, expiry: str) -> RenderedMail:
    loc = normalize_locale(locale)
    t = TEXTS[loc]
    prefix = _LINK_PREFIX[kind]
    intro = _fmt(t, f"{prefix}_intro")
    action = _fmt(t, f"{prefix}_action")
    ignore = _fmt(t, "ignore")
    text = "\n\n".join([intro, f"{action}: {link}", expiry, ignore, APP_NAME]) + "\n"
    html = _html(loc, [intro], link, action, _fmt(t, "link_hint"), [expiry, ignore])
    return RenderedMail(
        subject=_fmt(t, f"{prefix}_subject"),
        text=text,
        html=html,
        locale=loc,
        template=f"{kind}/{TEMPLATE_VERSION}",
    )


def render_verify_email(locale: str, link: str, *, hours: int) -> RenderedMail:
    expiry = _fmt(_texts(locale), "verify_expiry", hours=hours)
    return _link_mail("verify_email", locale, link, expiry)


def render_reset_password(locale: str, link: str, *, minutes: int) -> RenderedMail:
    expiry = _fmt(_texts(locale), "reset_expiry", minutes=minutes)
    return _link_mail("reset_password", locale, link, expiry)


def render_change_email(locale: str, link: str, *, hours: int) -> RenderedMail:
    expiry = _fmt(_texts(locale), "emailchange_expiry", hours=hours)
    return _link_mail("change_email", locale, link, expiry)


def _notice(locale: str, prefix: str, template: str) -> RenderedMail:
    loc = normalize_locale(locale)
    t = TEXTS[loc]
    body = _fmt(t, f"{prefix}_body")
    help_text = _fmt(t, "changed_help")
    return RenderedMail(
        subject=_fmt(t, f"{prefix}_subject"),
        text=f"{body}\n\n{help_text}\n\n{APP_NAME}\n",
        html=_html(loc, [body, help_text], None, None, None, []),
        locale=loc,
        template=f"{template}/{TEMPLATE_VERSION}",
    )


def render_email_change_started(locale: str) -> RenderedMail:
    return _notice(locale, "emailstart", "email_change_started")


def render_email_change_done(locale: str) -> RenderedMail:
    return _notice(locale, "emaildone", "email_change_done")


def render_password_added(locale: str) -> RenderedMail:
    return _notice(locale, "pwadded", "password_added")


def render_password_changed(locale: str) -> RenderedMail:
    loc = normalize_locale(locale)
    t = TEXTS[loc]
    body = _fmt(t, "changed_body")
    help_text = _fmt(t, "changed_help")
    return RenderedMail(
        subject=_fmt(t, "changed_subject"),
        text=f"{body}\n\n{help_text}\n\n{APP_NAME}\n",
        html=_html(loc, [body, help_text], None, None, None, []),
        locale=loc,
        template=f"password_changed/{TEMPLATE_VERSION}",
    )
