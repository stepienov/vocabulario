package com.vocabulario.app.ui.deletion

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.auth.GoogleAuthHelper
import com.vocabulario.app.auth.GoogleSignInCancelledException
import com.vocabulario.app.data.api.DeletionView
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.deletion.AccountDeletionRepository
import com.vocabulario.app.data.deletion.DELETION_METHOD_GOOGLE
import com.vocabulario.app.i18n.UiStrings
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Locale
import javax.inject.Inject

/** Hasło do cofnięcia tylko w pamięci; `null` = okno zamknięte. */
data class DeletionPendingUiState(
    val view: DeletionView? = null,
    val busy: Boolean = false,
    val error: String? = null,
    val cancelPassword: String? = null,
    /** Wniosek złożony przez Google cofamy też przez Google (bez pola hasła). */
    val cancelWithGoogle: Boolean = false,
)

/** Data z serwera (ISO-8601) w strefie i języku urządzenia; przy błędzie parsowania oryginał. */
internal fun formatDeletionInstant(iso: String, zone: ZoneId, locale: Locale): String = runCatching {
    OffsetDateTime.parse(iso).atZoneSameInstant(zone)
        .format(DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM, FormatStyle.SHORT).withLocale(locale))
}.getOrDefault(iso)

/** Ekran „konto czeka na usunięcie” (E-001/F-006/T-002 §5): status na wejściu i na przycisk, bez pollingu. */
@HiltViewModel
class DeletionPendingViewModel @Inject constructor(
    private val repository: AccountDeletionRepository,
    private val googleAuthHelper: GoogleAuthHelper,
    private val strings: UiStrings,
) : ViewModel() {

    private val _state = MutableStateFlow(DeletionPendingUiState())
    val state: StateFlow<DeletionPendingUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.receipt.collect { receipt ->
                _state.update {
                    it.copy(view = receipt?.deletion, cancelWithGoogle = receipt?.method == DELETION_METHOD_GOOGLE)
                }
            }
        }
        refresh()
    }

    fun refresh() {
        if (_state.value.busy) return
        run { repository.refreshStatus() }
    }

    fun cancelWithGoogle(activityContext: Context) {
        if (_state.value.busy) return
        run(afterError = { repository.refreshStatus() }) {
            try {
                repository.cancelWithGoogle(googleAuthHelper.provider(activityContext))
            } catch (_: GoogleSignInCancelledException) {
                // Anulowanie selektora nie jest błędem i nie wysyła żądania.
            }
        }
    }

    fun openCancel() {
        _state.update { it.copy(cancelPassword = "", error = null) }
    }

    fun closeCancel() {
        if (_state.value.busy) return
        _state.update { it.copy(cancelPassword = null) }
    }

    fun updateCancelPassword(value: String) {
        _state.update { if (it.cancelPassword == null) it else it.copy(cancelPassword = value, error = null) }
    }

    fun submitCancel() {
        val current = _state.value
        val password = current.cancelPassword ?: return
        if (current.busy) return
        if (password.isEmpty()) {
            _state.update { it.copy(error = strings.get(R.string.err_password_required)) }
            return
        }
        run(afterError = { repository.refreshStatus() }) {
            repository.cancel(password)
            _state.update { it.copy(cancelPassword = null) }
        }
    }

    private fun run(afterError: (suspend () -> Unit)? = null, block: suspend () -> Unit) {
        viewModelScope.launch {
            _state.update { it.copy(busy = true, error = null) }
            try {
                block()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(error = e.userMessage(strings, R.string.err_account_request_failed)) }
                runCatching { afterError?.invoke() }
            } finally {
                _state.update { it.copy(busy = false) }
            }
        }
    }
}
