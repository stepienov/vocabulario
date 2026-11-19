package com.vocabulario.app.data

import com.vocabulario.app.data.api.EmailChangeRequestBody
import com.vocabulario.app.data.api.EmailChangeResponse
import com.vocabulario.app.data.api.EmailVerificationStatusResponse
import com.vocabulario.app.data.api.RecentAuthPasswordRequest
import com.vocabulario.app.data.api.MailStatusResponse
import com.vocabulario.app.data.api.PasswordChangeRequest
import com.vocabulario.app.data.api.PasswordResetRequestBody
import com.vocabulario.app.data.api.UserResponse
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.session.SessionCoordinator
import com.vocabulario.app.data.session.SessionInstallException
import com.vocabulario.app.data.session.SessionState
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import java.util.Locale
import javax.inject.Inject
import javax.inject.Singleton

/** Minimalna długość nowego hasła przy resecie i zmianie (F-004/T-001, Argon2id). */
const val NEW_PASSWORD_MIN_CHARS = 15
const val PASSWORD_MAX_CHARS = 128

/** Język maila: UI aplikacji, a przed pierwszym profilem język systemu. */
internal fun TokenStore.mailLocale(): String = peekAppLang().ifBlank { Locale.getDefault().toLanguageTag() }

/** Wymóg potwierdzenia dotyczy tylko aktywnej sesji tego samego właściciela. */
internal fun verificationRequiredFor(requiredOwner: String?, state: SessionState): Boolean {
    if (requiredOwner == null || state !is SessionState.Active) return false
    return state.ownerUserId == null || state.ownerUserId == requiredOwner
}

/**
 * Stan bramki weryfikacji adresu (F-004/T-002 krok 4). Bez zależności od API, żeby interceptor
 * OkHttp mógł go ustawić po 403 bez cyklu w grafie Hilt.
 */
@Singleton
class EmailVerificationGate @Inject constructor(
    private val tokenStore: TokenStore,
    private val sessionCoordinator: SessionCoordinator,
) {
    val required: Flow<Boolean> =
        combine(tokenStore.verificationRequiredOwner, sessionCoordinator.state, ::verificationRequiredFor)
            .distinctUntilChanged()

    fun isRequired(): Boolean =
        verificationRequiredFor(tokenStore.verificationRequiredOwner.value, sessionCoordinator.state.value)

    /** 403 `email_verification_required`: zmiana uprawnienia, nie wylogowanie. */
    fun onServerRequired() {
        val state = sessionCoordinator.state.value as? SessionState.Active ?: return
        state.ownerUserId?.let { tokenStore.setVerificationRequiredOwner(it) }
    }

    /** Odpowiedź `/me` innego niż obecny właściciel (spóźniona po zmianie konta) jest pomijana. */
    fun apply(me: UserResponse) {
        val owner = (sessionCoordinator.state.value as? SessionState.Active)?.ownerUserId
        if (owner != null && owner != me.id) return
        tokenStore.setVerificationRequiredOwner(me.id.takeIf { me.email_verification_required })
    }
}

class StaleAccountResponseException : Exception("account response belongs to a different owner")

/** Ostatnia odpowiedź `/me` właściciela; [fetchedAtMs] pozwala oznaczyć dane jako nieświeże. */
data class CachedAccount(val me: UserResponse, val fetchedAtMs: Long)

/** Cache dotyczy wyłącznie aktywnego właściciela sesji: dane A nie pokażą się po logowaniu B. */
internal fun cachedFor(cache: CachedAccount?, state: SessionState): CachedAccount? {
    val owner = (state as? SessionState.Active)?.ownerUserId ?: return null
    return cache?.takeIf { it.me.id == owner }
}

/** Konto, poczta i hasło (E-001/F-004/T-002 §3–5). Bez pollingu: odczyt na żądanie. */
@Singleton
class AccountRepository @Inject constructor(
    private val api: VocabularioApi,
    private val tokenStore: TokenStore,
    private val sessionCoordinator: SessionCoordinator,
    private val gate: EmailVerificationGate,
) {
    @Volatile
    private var cache: CachedAccount? = null

    suspend fun refreshAccount(): UserResponse {
        val me = api.me()
        gate.apply(me)
        val owner = (sessionCoordinator.state.value as? SessionState.Active)?.ownerUserId
        // Spóźniona odpowiedź poprzedniego właściciela nie może trafić do ekranu nowego konta.
        if (owner != null && owner != me.id) throw StaleAccountResponseException()
        if (owner != null) cache = CachedAccount(me, System.currentTimeMillis())
        return me
    }

    /** Ostatnio pobrane dane tego właściciela (tylko w pamięci procesu); `null` po zmianie konta. */
    fun lastKnownAccount(): CachedAccount? = cachedFor(cache, sessionCoordinator.state.value)

    /** Język maila: UI aplikacji, a przed pierwszym profilem język systemu. */
    fun mailLocale(): String = tokenStore.mailLocale()

    suspend fun requestVerificationMail(): MailStatusResponse = api.emailVerificationRequest()

    suspend fun verificationStatus(): EmailVerificationStatusResponse = api.emailVerificationStatus()

    /** Zawsze neutralna odpowiedź: nie zdradza, czy konto istnieje. */
    suspend fun requestPasswordReset(email: String): MailStatusResponse =
        api.passwordResetRequest(PasswordResetRequestBody(email.trim(), mailLocale()))

    /** Hasło jako świeży dowód, potem prośba; ten sam `requestId` przy powtórzeniu tych samych danych. */
    suspend fun requestEmailChange(newEmail: String, password: String, requestId: String): EmailChangeResponse {
        val proof = api.recentAuthPassword(RecentAuthPasswordRequest(password, "change_email"))
        return api.emailChangeRequest(EmailChangeRequestBody(newEmail.trim(), proof.recent_auth_token, requestId))
    }

    suspend fun currentEmailChange(): EmailChangeResponse? =
        api.emailChangeCurrent().change?.takeIf { it.status == "pending" }

    suspend fun resendEmailChange(id: String): EmailChangeResponse = api.emailChangeResend(id)

    suspend fun cancelEmailChange(id: String) {
        api.emailChangeCancel(id)
    }

    /** Inne sesje kończą się na serwerze; ta dostaje nową parę tokenów tej samej sesji. */
    suspend fun changePassword(current: String, new: String) {
        val tokens = api.passwordChange(PasswordChangeRequest(current, new))
        if (!sessionCoordinator.installRenewed(tokens)) throw SessionInstallException("renewed pair not stored")
        runCatching { refreshAccount() }
    }
}
