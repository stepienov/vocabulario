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
)

TEXTS: dict[str, dict[str, str]] = {
    "en": {
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


def _link_mail(kind: str, locale: str, link: str, expiry: str) -> RenderedMail:
    loc = normalize_locale(locale)
    t = TEXTS[loc]
    prefix = "verify" if kind == "verify_email" else "reset"
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
