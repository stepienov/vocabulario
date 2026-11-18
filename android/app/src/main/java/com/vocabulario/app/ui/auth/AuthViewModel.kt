package com.vocabulario.app.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.auth.GoogleAuthHelper
import androidx.annotation.StringRes
import com.vocabulario.app.data.AccountRepository
import com.vocabulario.app.data.AuthRepository
import com.vocabulario.app.data.OtherAccountDataException
import com.vocabulario.app.data.UnclaimedLocalDataException
import com.vocabulario.app.data.BlockingBusy
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.NEW_PASSWORD_MIN_CHARS
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.session.AuthNotice
import com.vocabulario.app.data.session.LogoutConsent
import com.vocabulario.app.data.session.RevocationQueueFullException
import com.vocabulario.app.data.session.RevocationSummary
import com.vocabulario.app.data.session.SessionCoordinator
import com.vocabulario.app.data.session.SessionState
import com.vocabulario.app.data.session.UnsentChangesException
import com.vocabulario.app.data.session.authNotice
import com.vocabulario.app.i18n.UiStrings
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val learningRepository: LearningRepository,
    private val googleAuthHelper: GoogleAuthHelper,
    private val strings: UiStrings,
    private val blockingBusy: BlockingBusy,
    private val accountRepository: AccountRepository,
    sessionCoordinator: SessionCoordinator,
) : ViewModel() {

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private val _debugLoginError = MutableStateFlow<String?>(null)
    val debugLoginError: StateFlow<String?> = _debugLoginError.asStateFlow()

    /** Liczba niewysłanych zmian w danych bez właściciela; null = brak dialogu. */
    private val _unclaimedData = MutableStateFlow<Int?>(null)
    val unclaimedData: StateFlow<Int?> = _unclaimedData.asStateFlow()

    private val noticeRefresh = MutableStateFlow(0)

    /** Neutralny komunikat (nie błąd), np. potwierdzone wylogowanie na serwerze. */
    private val _infoMessage = MutableStateFlow<String?>(null)
    val infoMessage: StateFlow<String?> = _infoMessage.asStateFlow()

    /** Odwołania sesji na serwerze: oczekujące i zakończone bez potwierdzenia. */
    val revocations: StateFlow<RevocationSummary> = authRepository.revocationSummary

    /** Ustawiane po logout tego ekranu, żeby potwierdzenie dotyczyło właśnie tego wylogowania. */
    private var awaitingServerSignOut = false

    init {
        viewModelScope.launch {
            var previous = revocations.value
            revocations.collect { current ->
                if (awaitingServerSignOut && previous.pending > 0 && current.pending == 0) {
                    awaitingServerSignOut = false
                    if (current.unconfirmed <= previous.unconfirmed) {
                        _infoMessage.value = strings.get(R.string.auth_revocation_confirmed)
                    }
                }
                previous = current
            }
        }
    }

    fun dismissUnconfirmedRevocations() {
        viewModelScope.launch { authRepository.dismissUnconfirmedRevocations() }
    }

    /** Flaga przed wywołaniem, bo worker może potwierdzić odwołanie, zanim logout wróci. */
    private suspend fun logoutAndTrack(consent: LogoutConsent) {
        _infoMessage.value = null
        awaitingServerSignOut = true
        try {
            if (!authRepository.logout(consent)) awaitingServerSignOut = false
        } catch (e: Throwable) {
            awaitingServerSignOut = false
            throw e
        }
    }

    /** Ostrzeżenie o niewysłanych zmianach przy logout z ustawień; null = brak dialogu. */
    private val _logoutPrompt = MutableStateFlow<LogoutPrompt?>(null)
    val logoutPrompt: StateFlow<LogoutPrompt?> = _logoutPrompt.asStateFlow()

    /** Dialog „Nie pamiętam hasła”; null = zamknięty. */
    private val _forgotPassword = MutableStateFlow<ForgotPasswordState?>(null)
    val forgotPassword: StateFlow<ForgotPasswordState?> = _forgotPassword.asStateFlow()

    fun openForgotPassword(prefillEmail: String) {
        _forgotPassword.value = ForgotPasswordState(email = prefillEmail.trim())
    }

    fun updateForgotPasswordEmail(value: String) {
        _forgotPassword.value = _forgotPassword.value?.copy(email = value, error = null)
    }

    fun closeForgotPassword() {
        _forgotPassword.value = null
    }

    /** Odpowiedź serwera jest neutralna (202 także dla nieznanego adresu), więc komunikat też. */
    fun sendForgotPassword() {
        val current = _forgotPassword.value ?: return
        val email = current.email.trim()
        if (current.sending || current.sent) return
        if (email.isBlank()) {
            _forgotPassword.value = current.copy(error = strings.get(R.string.err_email_required))
            return
        }
        if (!email.contains('@')) {
            _forgotPassword.value = current.copy(error = strings.get(R.string.err_email_invalid))
            return
        }
        viewModelScope.launch {
            _forgotPassword.value = current.copy(sending = true, error = null)
            try {
                accountRepository.requestPasswordReset(email)
                _forgotPassword.value = _forgotPassword.value?.copy(sending = false, sent = true)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _forgotPassword.value = _forgotPassword.value?.copy(
                    sending = false,
                    error = e.userMessage(strings, R.string.err_account_request_failed),
                )
            }
        }
    }

    /** Logout z ustawień: bez niewysłanych zmian od razu, inaczej dialog z decyzją użytkownika. */
    fun requestLogout(onDone: suspend () -> Unit) {
        viewModelScope.launch {
            blockingBusy.run { attemptLogout(LogoutConsent.RequireEmpty, LogoutPromptReason.INITIAL, onDone) }
        }
    }

    /** Błąd lub brak sieci przy synchronizacji nie jest zgodą na odrzucenie: wraca ostrzeżenie. */
    fun syncAndLogout(onDone: suspend () -> Unit) {
        viewModelScope.launch {
            blockingBusy.run {
                _logoutPrompt.value = null
                try {
                    learningRepository.syncNow(awaitLock = true)
                } catch (e: CancellationException) {
                    throw e
                } catch (_: Exception) {
                    // Wynik oceni bariera logoutu na podstawie kolejek.
                }
                attemptLogout(LogoutConsent.RequireEmpty, LogoutPromptReason.SYNC_INCOMPLETE, onDone)
            }
        }
    }

    fun askDiscardConfirmation() {
        _logoutPrompt.value = _logoutPrompt.value?.copy(confirmDiscard = true)
    }

    /** Odrzuca tylko snapshot z ostrzeżenia; nowa praca wymaga ponownej decyzji. */
    fun discardAndLogout(onDone: suspend () -> Unit) {
        val prompt = _logoutPrompt.value ?: return
        viewModelScope.launch {
            blockingBusy.run {
                _logoutPrompt.value = null
                attemptLogout(
                    LogoutConsent.DiscardConfirmed(prompt.fingerprint),
                    LogoutPromptReason.CHANGED,
                    onDone,
                )
            }
        }
    }

    fun cancelLogout() {
        _logoutPrompt.value = null
    }

    private suspend fun attemptLogout(
        consent: LogoutConsent,
        reasonIfUnsent: LogoutPromptReason,
        onDone: suspend () -> Unit,
    ) {
        try {
            logoutAndTrack(consent)
        } catch (e: CancellationException) {
            throw e
        } catch (e: UnsentChangesException) {
            _logoutPrompt.value = LogoutPrompt(e.unsentCount, e.fingerprint, reasonIfUnsent)
            return
        } catch (_: Exception) {
            // Nieudany trwały zapis wylogowania nie może udawać sukcesu.
            return
        }
        _logoutPrompt.value = null
        onDone()
    }

    /** Stan sesji i danych na urządzeniu widoczny nad formularzem logowania. */
    val notice: StateFlow<AuthNotice?> = combine(sessionCoordinator.state, noticeRefresh) { state, _ ->
        loadNotice(state)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    private suspend fun loadNotice(state: SessionState): AuthNotice? = try {
        authNotice(state, authRepository.ownerSnapshot())
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        null
    }

    fun clearError() {
        _errorMessage.value = null
        _debugLoginError.value = null
        _infoMessage.value = null
    }

    fun dismissUnclaimedData() {
        _unclaimedData.value = null
    }

    fun discardUnclaimedData() {
        viewModelScope.launch {
            blockingBusy.run {
                val discarded = try {
                    authRepository.discardUnclaimedLocalData()
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    false
                }
                _unclaimedData.value = null
                noticeRefresh.value++
                _errorMessage.value = strings.get(
                    if (discarded) R.string.legacy_data_discarded else R.string.legacy_data_discard_failed,
                )
            }
        }
    }

    /** Jawne wyjście z sesji wymagającej reauth/odzyskania: usuwa pokazane w ostrzeżeniu dane. */
    fun signOutOnDevice(acceptedFingerprint: String) {
        viewModelScope.launch {
            blockingBusy.run {
                val message = try {
                    logoutAndTrack(LogoutConsent.DiscardConfirmed(acceptedFingerprint))
                    R.string.auth_signed_out_device
                } catch (e: CancellationException) {
                    throw e
                } catch (_: UnsentChangesException) {
                    R.string.logout_unsent_changed
                } catch (_: Exception) {
                    R.string.auth_sign_out_device_failed
                }
                noticeRefresh.value++
                _errorMessage.value = strings.get(message)
            }
        }
    }

    fun retrySessionRecovery(onRecovered: suspend (needsOnboarding: Boolean) -> Unit) {
        viewModelScope.launch {
            blockingBusy.run {
                _errorMessage.value = null
                val recovered = try {
                    authRepository.retrySessionRecovery()
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    false
                }
                if (recovered) {
                    finishSignIn(onRecovered)
                } else {
                    noticeRefresh.value++
                    _errorMessage.value = strings.get(R.string.auth_recovery_retry_failed)
                }
            }
        }
    }

    private suspend fun finishSignIn(onSuccess: suspend (needsOnboarding: Boolean) -> Unit) {
        val needsOnboarding = runCatching { !authRepository.hasProfile() }.getOrDefault(false)
        if (!needsOnboarding) {
            runCatching { authRepository.ensureActiveProfile() }
            runCatching { learningRepository.applyAppLocaleFromActiveProfile() }
        }
        runCatching { learningRepository.syncThemeFromSettings() }
        onSuccess(needsOnboarding)
    }

    private fun authFailureMessage(error: Throwable, @StringRes defaultRes: Int): String? = when (error) {
        is UnclaimedLocalDataException -> {
            _unclaimedData.value = error.unsentCount
            null
        }
        is OtherAccountDataException -> strings.get(R.string.err_login_other_account)
        is RevocationQueueFullException -> strings.get(R.string.auth_revocation_queue_full)
        else -> error.userMessage(strings, defaultRes)
    }

    private fun validate(email: String, password: String, isRegister: Boolean): String? {
        val trimmedEmail = email.trim()
        if (trimmedEmail.isBlank()) return strings.get(R.string.err_email_required)
        if (!trimmedEmail.contains("@")) return strings.get(R.string.err_email_invalid)
        if (password.isBlank()) return strings.get(R.string.err_password_required)
        if (isRegister && password.codePointCount(0, password.length) < NEW_PASSWORD_MIN_CHARS) {
            return strings.get(R.string.err_password_short)
        }
        return null
    }

    fun login(email: String, password: String, onSuccess: suspend (needsOnboarding: Boolean) -> Unit) {
        validate(email, password, isRegister = false)?.let {
            _errorMessage.value = it
            return
        }
        viewModelScope.launch {
            blockingBusy.run {
                _errorMessage.value = null
                _debugLoginError.value = null
                runCatching {
                    authRepository.login(email.trim(), password)
                }.onSuccess {
                    finishSignIn(onSuccess)
                }.onFailure {
                    if (com.vocabulario.app.BuildConfig.DEBUG) {
                        _debugLoginError.value = it.javaClass.simpleName + ": " + (it.message ?: it.toString())
                    }
                    _errorMessage.value = authFailureMessage(it, R.string.err_login)
                }
            }
        }
    }

    fun register(email: String, password: String, onSuccess: suspend () -> Unit) {
        validate(email, password, isRegister = true)?.let {
            _errorMessage.value = it
            return
        }
        viewModelScope.launch {
            blockingBusy.run {
                _errorMessage.value = null
                runCatching {
                    authRepository.register(email.trim(), password)
                }.onSuccess { onSuccess() }
                    .onFailure {
                        _errorMessage.value = authFailureMessage(it, R.string.err_register)
                    }
            }
        }
    }

    fun googleSignIn(activityContext: android.content.Context, onSuccess: suspend (needsOnboarding: Boolean) -> Unit) {
        viewModelScope.launch {
            _errorMessage.value = null
            val idToken = runCatching { googleAuthHelper.signIn(activityContext) }
                .onFailure {
                    _errorMessage.value = it.userMessage(strings, R.string.err_google_login)
                }
                .getOrNull() ?: return@launch
            blockingBusy.run {
                runCatching {
                    authRepository.googleLogin(idToken)
                }.onSuccess {
                    finishSignIn(onSuccess)
                }.onFailure {
                    _errorMessage.value = authFailureMessage(it, R.string.err_google_login)
                }
            }
        }
    }
}

enum class LogoutPromptReason {
    /** Pierwsze ostrzeżenie przed logout. */
    INITIAL,

    /** Po synchronizacji nadal zostały niewysłane zmiany (brak sieci, błąd, zmiany do decyzji). */
    SYNC_INCOMPLETE,

    /** Od potwierdzenia pojawiła się nowa praca; zgoda jej nie obejmowała. */
    CHANGED,
}

data class LogoutPrompt(
    val unsentCount: Int,
    val fingerprint: String,
    val reason: LogoutPromptReason,
    val confirmDiscard: Boolean = false,
)

data class ForgotPasswordState(
    val email: String,
    val sending: Boolean = false,
    val sent: Boolean = false,
    val error: String? = null,
)
