package com.vocabulario.app.ui.settings

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.auth.GoogleAuthHelper
import com.vocabulario.app.auth.GoogleSignInCancelledException
import com.vocabulario.app.data.AccountRepository
import com.vocabulario.app.data.NEW_PASSWORD_MIN_CHARS
import com.vocabulario.app.data.PASSWORD_MAX_CHARS
import com.vocabulario.app.data.api.EmailChangeResponse
import com.vocabulario.app.data.api.UserResponse
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.deletion.AccountDeletionRepository
import com.vocabulario.app.i18n.UiStrings
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID
import javax.inject.Inject

data class AccountUiState(
    val email: String? = null,
    val emailVerified: Boolean = true,
    val hasPassword: Boolean = false,
    val hasGoogle: Boolean = false,
    val googleEmail: String? = null,
    /** Stary format hasła: zmiana wymaga starego hasła, więc prowadzimy do resetu. */
    val passwordUpgradeRequired: Boolean = false,
    val resetSending: Boolean = false,
    /** Oczekująca zmiana adresu (bez pollingu: odczyt przy wejściu i po akcjach). */
    val pendingChange: EmailChangeResponse? = null,
    val changeBusy: Boolean = false,
    val loading: Boolean = false,
    /** Brak sieci lub błąd `/me`: sekcja pokazuje komunikat zamiast danych. */
    val unavailable: Boolean = false,
    /** Dane z cache (ostatnio pobrane): akcje bezpieczeństwa i usuwania wymagają sieci, więc są wyłączone. */
    val stale: Boolean = false,
    val info: String? = null,
)

internal fun AccountUiState.withAccount(me: UserResponse, stale: Boolean) = copy(
    email = me.email,
    emailVerified = me.email_verified,
    hasPassword = "password" in me.login_methods,
    hasGoogle = "google" in me.login_methods,
    googleEmail = me.google_email,
    passwordUpgradeRequired = me.password_upgrade_required,
    unavailable = false,
    stale = stale,
)

/** Hasła tylko w pamięci ViewModelu; nie trafiają do SavedStateHandle ani logów. */
data class ChangePasswordUiState(
    val current: String = "",
    val new: String = "",
    val repeat: String = "",
    val busy: Boolean = false,
    val error: String? = null,
)

internal enum class NewPasswordProblem { CURRENT_EMPTY, TOO_SHORT, TOO_LONG, MISMATCH }

/**
 * Hasło tylko w pamięci; konto bez hasła potwierdza zmianę kontem Google ([usesGoogle]).
 * `requestId` zmienia się razem z adresem, więc ponowienie jest idempotentne.
 */
data class ChangeEmailUiState(
    val newEmail: String = "",
    val password: String = "",
    val usesGoogle: Boolean = false,
    val requestId: String = UUID.randomUUID().toString(),
    val busy: Boolean = false,
    val error: String? = null,
)

internal enum class NewEmailProblem { EMPTY, INVALID, UNCHANGED, PASSWORD_EMPTY }

/** Dołączenie Google wymaga bieżącego hasła; ono i błędy żyją tylko w pamięci ViewModelu. */
data class LinkGoogleUiState(
    val password: String = "",
    val busy: Boolean = false,
    val error: String? = null,
)

/** Hasło dla konta Google-only; zatwierdzenie poprzedza wybór konta Google. */
data class AddPasswordUiState(
    val new: String = "",
    val repeat: String = "",
    val busy: Boolean = false,
    val error: String? = null,
)

/** Hasło tylko w pamięci; [unsentCount] to niewysłane zmiany z tego urządzenia (inne urządzenia nie są znane). */
data class DeleteAccountUiState(
    val password: String = "",
    val usesGoogle: Boolean = false,
    val confirmed: Boolean = false,
    val unsentCount: Int = 0,
    val busy: Boolean = false,
    val error: String? = null,
)

internal fun validateNewEmail(
    current: String?,
    new: String,
    password: String,
    passwordRequired: Boolean = true,
): NewEmailProblem? {
    val email = new.trim()
    return when {
        email.isEmpty() -> NewEmailProblem.EMPTY
        !email.contains('@') || email.startsWith('@') || email.endsWith('@') || email.any { it.isWhitespace() } ->
            NewEmailProblem.INVALID
        current != null && email.equals(current.trim(), ignoreCase = true) -> NewEmailProblem.UNCHANGED
        passwordRequired && password.isEmpty() -> NewEmailProblem.PASSWORD_EMPTY
        else -> null
    }
}

internal fun validateNewPassword(current: String, new: String, repeat: String): NewPasswordProblem? =
    if (current.isEmpty()) NewPasswordProblem.CURRENT_EMPTY else validatePasswordPair(new, repeat)

internal fun validatePasswordPair(new: String, repeat: String): NewPasswordProblem? {
    val length = new.codePointCount(0, new.length)
    return when {
        length < NEW_PASSWORD_MIN_CHARS -> NewPasswordProblem.TOO_SHORT
        length > PASSWORD_MAX_CHARS -> NewPasswordProblem.TOO_LONG
        new != repeat -> NewPasswordProblem.MISMATCH
        else -> null
    }
}

/** Sekcja „Konto” w Ustawieniach (E-001/F-006/T-001, F-004/T-002 §5). */
@HiltViewModel
class AccountSettingsViewModel @Inject constructor(
    private val accountRepository: AccountRepository,
    private val deletionRepository: AccountDeletionRepository,
    private val googleAuthHelper: GoogleAuthHelper,
    private val strings: UiStrings,
) : ViewModel() {

    private val _linkGoogle = MutableStateFlow<LinkGoogleUiState?>(null)
    val linkGoogle: StateFlow<LinkGoogleUiState?> = _linkGoogle.asStateFlow()

    private val _addPassword = MutableStateFlow<AddPasswordUiState?>(null)
    val addPassword: StateFlow<AddPasswordUiState?> = _addPassword.asStateFlow()

    private val _deleteAccount = MutableStateFlow<DeleteAccountUiState?>(null)
    val deleteAccount: StateFlow<DeleteAccountUiState?> = _deleteAccount.asStateFlow()

    private val _account = MutableStateFlow(AccountUiState())
    val account: StateFlow<AccountUiState> = _account.asStateFlow()

    private val _changePassword = MutableStateFlow<ChangePasswordUiState?>(null)
    val changePassword: StateFlow<ChangePasswordUiState?> = _changePassword.asStateFlow()

    private val _changeEmail = MutableStateFlow<ChangeEmailUiState?>(null)
    val changeEmail: StateFlow<ChangeEmailUiState?> = _changeEmail.asStateFlow()

    fun load() {
        if (_account.value.loading) return
        viewModelScope.launch {
            _account.update { it.copy(loading = true) }
            try {
                val me = accountRepository.refreshAccount()
                _account.update { it.withAccount(me, stale = false) }
                loadPendingChange()
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                val cached = accountRepository.lastKnownAccount()
                _account.update {
                    when {
                        cached != null -> it.withAccount(cached.me, stale = true)
                        else -> it.copy(unavailable = it.email == null)
                    }
                }
            } finally {
                _account.update { it.copy(loading = false) }
            }
        }
    }

    fun sendPasswordReset() {
        val state = _account.value
        val email = state.email ?: return
        if (state.resetSending) return
        viewModelScope.launch {
            _account.update { it.copy(resetSending = true, info = null) }
            try {
                accountRepository.requestPasswordReset(email)
                _account.update { it.copy(info = strings.get(R.string.auth_forgot_password_sent, email)) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _account.update {
                    it.copy(info = e.userMessage(strings, R.string.err_account_request_failed))
                }
            } finally {
                _account.update { it.copy(resetSending = false) }
            }
        }
    }

    fun openChangePassword() {
        _account.update { it.copy(info = null) }
        _changePassword.value = ChangePasswordUiState()
    }

    fun closeChangePassword() {
        if (_changePassword.value?.busy == true) return
        _changePassword.value = null
    }

    fun updateChangePassword(current: String? = null, new: String? = null, repeat: String? = null) {
        _changePassword.update { state ->
            state?.copy(
                current = current ?: state.current,
                new = new ?: state.new,
                repeat = repeat ?: state.repeat,
                error = null,
            )
        }
    }

    fun submitChangePassword() {
        val form = _changePassword.value ?: return
        if (form.busy) return
        val problem = validateNewPassword(form.current, form.new, form.repeat)
        if (problem != null) {
            _changePassword.value = form.copy(error = problemMessage(problem))
            return
        }
        viewModelScope.launch {
            _changePassword.value = form.copy(busy = true, error = null)
            try {
                accountRepository.changePassword(form.current, form.new)
                _changePassword.value = null
                _account.update { it.copy(info = strings.get(R.string.account_password_changed)) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _changePassword.update {
                    it?.copy(busy = false, error = e.userMessage(strings, R.string.err_account_request_failed))
                }
            }
        }
    }

    fun openDeleteAccount() {
        _account.update { it.copy(info = null) }
        val googleOnly = !_account.value.hasPassword && _account.value.hasGoogle
        viewModelScope.launch {
            val unsent = runCatching { deletionRepository.unsentLocalCount() }.getOrDefault(0)
            _deleteAccount.value = DeleteAccountUiState(unsentCount = unsent, usesGoogle = googleOnly)
        }
    }

    fun closeDeleteAccount() {
        if (_deleteAccount.value?.busy == true) return
        _deleteAccount.value = null
    }

    fun updateDeleteAccount(password: String? = null, confirmed: Boolean? = null) {
        _deleteAccount.update { state ->
            state?.copy(
                password = password ?: state.password,
                confirmed = confirmed ?: state.confirmed,
                error = null,
            )
        }
    }

    fun submitDeleteAccount(activityContext: Context) {
        val form = _deleteAccount.value ?: return
        val email = _account.value.email ?: return
        if (form.busy || !form.confirmed) return
        if (!form.usesGoogle && form.password.isEmpty()) {
            _deleteAccount.value = form.copy(error = strings.get(R.string.err_password_required))
            return
        }
        viewModelScope.launch {
            _deleteAccount.value = form.copy(busy = true, error = null)
            try {
                if (form.usesGoogle) {
                    deletionRepository.requestWithGoogle(email, googleAuthHelper.provider(activityContext))
                } else {
                    deletionRepository.request(email, form.password)
                }
                _deleteAccount.value = null
            } catch (e: CancellationException) {
                throw e
            } catch (_: GoogleSignInCancelledException) {
                _deleteAccount.update { it?.copy(busy = false) }
            } catch (e: Exception) {
                _deleteAccount.update {
                    it?.copy(busy = false, error = e.userMessage(strings, R.string.err_account_request_failed))
                }
            }
        }
    }

    fun openLinkGoogle() {
        _account.update { it.copy(info = null) }
        _linkGoogle.value = LinkGoogleUiState()
    }

    fun closeLinkGoogle() {
        if (_linkGoogle.value?.busy == true) return
        _linkGoogle.value = null
    }

    fun updateLinkGoogle(password: String) {
        _linkGoogle.update { it?.copy(password = password, error = null) }
    }

    fun submitLinkGoogle(activityContext: Context) {
        val form = _linkGoogle.value ?: return
        if (form.busy) return
        if (form.password.isEmpty()) {
            _linkGoogle.value = form.copy(error = strings.get(R.string.err_password_required))
            return
        }
        viewModelScope.launch {
            _linkGoogle.value = form.copy(busy = true, error = null)
            try {
                accountRepository.linkGoogle(form.password, googleAuthHelper.provider(activityContext))
                _linkGoogle.value = null
                _account.update { it.copy(info = strings.get(R.string.account_link_google_done)) }
                load()
            } catch (e: CancellationException) {
                throw e
            } catch (_: GoogleSignInCancelledException) {
                _linkGoogle.update { it?.copy(busy = false) }
            } catch (e: Exception) {
                _linkGoogle.update {
                    it?.copy(busy = false, error = e.userMessage(strings, R.string.err_account_request_failed))
                }
            }
        }
    }

    fun openAddPassword() {
        _account.update { it.copy(info = null) }
        _addPassword.value = AddPasswordUiState()
    }

    fun closeAddPassword() {
        if (_addPassword.value?.busy == true) return
        _addPassword.value = null
    }

    fun updateAddPassword(new: String? = null, repeat: String? = null) {
        _addPassword.update { state ->
            state?.copy(new = new ?: state.new, repeat = repeat ?: state.repeat, error = null)
        }
    }

    fun submitAddPassword(activityContext: Context) {
        val form = _addPassword.value ?: return
        if (form.busy) return
        val problem = validatePasswordPair(form.new, form.repeat)
        if (problem != null) {
            _addPassword.value = form.copy(error = problemMessage(problem))
            return
        }
        viewModelScope.launch {
            _addPassword.value = form.copy(busy = true, error = null)
            try {
                accountRepository.addPassword(form.new, googleAuthHelper.provider(activityContext))
                _addPassword.value = null
                _account.update { it.copy(info = strings.get(R.string.account_password_added)) }
                load()
            } catch (e: CancellationException) {
                throw e
            } catch (_: GoogleSignInCancelledException) {
                _addPassword.update { it?.copy(busy = false) }
            } catch (e: Exception) {
                _addPassword.update {
                    it?.copy(busy = false, error = e.userMessage(strings, R.string.err_account_request_failed))
                }
            }
        }
    }

    private suspend fun loadPendingChange() {
        try {
            val pending = accountRepository.currentEmailChange()
            _account.update { it.copy(pendingChange = pending) }
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            // Błąd odczytu nie ukrywa już pokazanej zmiany; następne wejście spróbuje ponownie.
        }
    }

    fun openChangeEmail() {
        _account.update { it.copy(info = null) }
        _changeEmail.value = ChangeEmailUiState(usesGoogle = !_account.value.hasPassword && _account.value.hasGoogle)
    }

    fun closeChangeEmail() {
        if (_changeEmail.value?.busy == true) return
        _changeEmail.value = null
    }

    fun updateChangeEmail(newEmail: String? = null, password: String? = null) {
        _changeEmail.update { state ->
            state?.copy(
                newEmail = newEmail ?: state.newEmail,
                password = password ?: state.password,
                requestId = if (newEmail != null && newEmail != state.newEmail) {
                    UUID.randomUUID().toString()
                } else {
                    state.requestId
                },
                error = null,
            )
        }
    }

    fun submitChangeEmail(activityContext: Context) {
        val form = _changeEmail.value ?: return
        if (form.busy) return
        val problem = validateNewEmail(_account.value.email, form.newEmail, form.password, !form.usesGoogle)
        if (problem != null) {
            _changeEmail.value = form.copy(error = emailProblemMessage(problem))
            return
        }
        viewModelScope.launch {
            _changeEmail.value = form.copy(busy = true, error = null)
            try {
                val created = if (form.usesGoogle) {
                    accountRepository.requestEmailChangeWithGoogle(
                        form.newEmail, form.requestId, googleAuthHelper.provider(activityContext),
                    )
                } else {
                    accountRepository.requestEmailChange(form.newEmail, form.password, form.requestId)
                }
                _changeEmail.value = null
                _account.update {
                    it.copy(
                        pendingChange = created,
                        info = strings.get(R.string.account_email_change_sent, created.new_email),
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (_: GoogleSignInCancelledException) {
                _changeEmail.update { it?.copy(busy = false) }
            } catch (e: Exception) {
                _changeEmail.update {
                    it?.copy(busy = false, error = e.userMessage(strings, R.string.err_account_request_failed))
                }
            }
        }
    }

    fun resendEmailChange() = pendingAction { id ->
        val updated = accountRepository.resendEmailChange(id)
        _account.update {
            it.copy(pendingChange = updated, info = strings.get(R.string.account_email_change_resent))
        }
    }

    fun cancelEmailChange() = pendingAction { id ->
        accountRepository.cancelEmailChange(id)
        _account.update {
            it.copy(pendingChange = null, info = strings.get(R.string.account_email_change_cancelled))
        }
    }

    private fun pendingAction(block: suspend (String) -> Unit) {
        val state = _account.value
        val id = state.pendingChange?.change_id ?: return
        if (state.changeBusy) return
        viewModelScope.launch {
            _account.update { it.copy(changeBusy = true, info = null) }
            try {
                block(id)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _account.update { it.copy(info = e.userMessage(strings, R.string.err_account_request_failed)) }
                loadPendingChange()
            } finally {
                _account.update { it.copy(changeBusy = false) }
            }
        }
    }

    private fun emailProblemMessage(problem: NewEmailProblem): String = when (problem) {
        NewEmailProblem.EMPTY -> strings.get(R.string.err_email_required)
        NewEmailProblem.INVALID -> strings.get(R.string.err_email_invalid)
        NewEmailProblem.UNCHANGED -> strings.get(R.string.err_email_unchanged)
        NewEmailProblem.PASSWORD_EMPTY -> strings.get(R.string.err_password_required)
    }

    private fun problemMessage(problem: NewPasswordProblem): String = when (problem) {
        NewPasswordProblem.CURRENT_EMPTY -> strings.get(R.string.err_password_required)
        NewPasswordProblem.TOO_SHORT -> strings.get(R.string.err_new_password_short)
        NewPasswordProblem.TOO_LONG -> strings.get(R.string.err_password_too_long)
        NewPasswordProblem.MISMATCH -> strings.get(R.string.err_passwords_mismatch)
    }
}
