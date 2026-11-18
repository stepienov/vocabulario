package com.vocabulario.app.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.AccountRepository
import com.vocabulario.app.data.NEW_PASSWORD_MIN_CHARS
import com.vocabulario.app.data.PASSWORD_MAX_CHARS
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.i18n.UiStrings
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AccountUiState(
    val email: String? = null,
    val emailVerified: Boolean = true,
    val hasPassword: Boolean = false,
    val hasGoogle: Boolean = false,
    val loading: Boolean = false,
    /** Brak sieci lub błąd `/me`: sekcja pokazuje komunikat zamiast danych. */
    val unavailable: Boolean = false,
    val info: String? = null,
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

internal fun validateNewPassword(current: String, new: String, repeat: String): NewPasswordProblem? {
    val length = new.codePointCount(0, new.length)
    return when {
        current.isEmpty() -> NewPasswordProblem.CURRENT_EMPTY
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
    private val strings: UiStrings,
) : ViewModel() {

    private val _account = MutableStateFlow(AccountUiState())
    val account: StateFlow<AccountUiState> = _account.asStateFlow()

    private val _changePassword = MutableStateFlow<ChangePasswordUiState?>(null)
    val changePassword: StateFlow<ChangePasswordUiState?> = _changePassword.asStateFlow()

    fun load() {
        if (_account.value.loading) return
        viewModelScope.launch {
            _account.update { it.copy(loading = true) }
            try {
                val me = accountRepository.refreshAccount()
                _account.update {
                    it.copy(
                        email = me.email,
                        emailVerified = me.email_verified,
                        hasPassword = "password" in me.login_methods,
                        hasGoogle = "google" in me.login_methods,
                        unavailable = false,
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                _account.update { it.copy(unavailable = it.email == null) }
            } finally {
                _account.update { it.copy(loading = false) }
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

    private fun problemMessage(problem: NewPasswordProblem): String = when (problem) {
        NewPasswordProblem.CURRENT_EMPTY -> strings.get(R.string.err_password_required)
        NewPasswordProblem.TOO_SHORT -> strings.get(R.string.err_new_password_short)
        NewPasswordProblem.TOO_LONG -> strings.get(R.string.err_password_too_long)
        NewPasswordProblem.MISMATCH -> strings.get(R.string.err_passwords_mismatch)
    }
}
