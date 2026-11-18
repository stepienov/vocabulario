package com.vocabulario.app.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.auth.GoogleAuthHelper
import androidx.annotation.StringRes
import com.vocabulario.app.data.AuthRepository
import com.vocabulario.app.data.OtherAccountDataException
import com.vocabulario.app.data.UnclaimedLocalDataException
import com.vocabulario.app.data.BlockingBusy
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.session.AuthNotice
import com.vocabulario.app.data.session.RevocationQueueFullException
import com.vocabulario.app.data.session.RevocationSummary
import com.vocabulario.app.data.session.SessionCoordinator
import com.vocabulario.app.data.session.SessionState
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
    private suspend fun logoutAndTrack() {
        _infoMessage.value = null
        awaitingServerSignOut = true
        try {
            if (!authRepository.logout()) awaitingServerSignOut = false
        } catch (e: Throwable) {
            awaitingServerSignOut = false
            throw e
        }
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

    /** Jawne wyjście z sesji wymagającej reauth/odzyskania: usuwa dane konta z tego urządzenia. */
    fun signOutOnDevice() {
        viewModelScope.launch {
            blockingBusy.run {
                val signedOut = try {
                    logoutAndTrack()
                    true
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    false
                }
                noticeRefresh.value++
                _errorMessage.value = strings.get(
                    if (signedOut) R.string.auth_signed_out_device else R.string.auth_sign_out_device_failed,
                )
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
        if (isRegister && password.length < 8) return strings.get(R.string.err_password_short)
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

    fun logout(onDone: suspend () -> Unit) {
        viewModelScope.launch {
            blockingBusy.run {
                // Nieudany trwały zapis wylogowania nie może udawać sukcesu.
                val loggedOut = try {
                    logoutAndTrack()
                    true
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    false
                }
                if (loggedOut) onDone()
            }
        }
    }
}
