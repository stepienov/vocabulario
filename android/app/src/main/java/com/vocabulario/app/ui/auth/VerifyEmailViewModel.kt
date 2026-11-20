package com.vocabulario.app.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.AccountRepository
import com.vocabulario.app.data.EmailVerificationGate
import com.vocabulario.app.data.api.EmailVerificationStatusResponse
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.i18n.UiStrings
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.time.OffsetDateTime
import javax.inject.Inject

enum class MailDelivery { NONE, SENDING, SENT, DELAYED, FAILED }

data class VerifyEmailUiState(
    val email: String? = null,
    val delivery: MailDelivery = MailDelivery.NONE,
    /** Zegar urządzenia (ms), od kiedy wolno wysłać ponownie; 0 = od razu. */
    val resendAtMillis: Long = 0L,
    val busy: Boolean = false,
    val info: String? = null,
    val error: String? = null,
)

internal fun deliveryOf(status: EmailVerificationStatusResponse): MailDelivery = when {
    status.delivery_delayed -> MailDelivery.DELAYED
    status.delivery_status == "queued" -> MailDelivery.SENDING
    status.delivery_status == "provider_accepted" || status.delivery_status == "delivered" -> MailDelivery.SENT
    status.delivery_status == "failed" -> MailDelivery.FAILED
    else -> MailDelivery.NONE
}

/** Termin ponownej wysyłki z serwera; przeszły lub nieczytelny = od razu. */
internal fun resendAtFrom(iso: String?, nowMillis: Long): Long {
    val at = iso?.let { runCatching { OffsetDateTime.parse(it).toInstant().toEpochMilli() }.getOrNull() }
        ?: return 0L
    return if (at > nowMillis) at else 0L
}

/**
 * Ekran bramki weryfikacji (F-004/T-002 §5). Bez pollingu: stan czytany przy wejściu,
 * powrocie do aplikacji i na przycisk. Potwierdzenie zdejmuje bramkę w [EmailVerificationGate].
 */
@HiltViewModel
class VerifyEmailViewModel @Inject constructor(
    private val accountRepository: AccountRepository,
    private val gate: EmailVerificationGate,
    private val strings: UiStrings,
) : ViewModel() {

    private val _state = MutableStateFlow(VerifyEmailUiState())
    val state: StateFlow<VerifyEmailUiState> = _state.asStateFlow()

    /** [userAsked] = przycisk „Sprawdź”; powrót do aplikacji nie pokazuje komunikatu „jeszcze nie”. */
    fun check(userAsked: Boolean) {
        if (_state.value.busy) return
        viewModelScope.launch {
            _state.update { it.copy(busy = true, error = null, info = if (userAsked) null else it.info) }
            try {
                val me = accountRepository.refreshAccount()
                _state.update { it.copy(email = me.email) }
                if (gate.isRequired()) {
                    val status = runCatching { accountRepository.verificationStatus() }.getOrNull()
                    _state.update { current ->
                        current.copy(
                            delivery = status?.let(::deliveryOf) ?: current.delivery,
                            resendAtMillis = status?.let { resendAtFrom(it.resend_available_at, now()) }
                                ?: current.resendAtMillis,
                            info = if (userAsked) strings.get(R.string.verify_email_not_yet) else current.info,
                        )
                    }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (userAsked) _state.update { it.copy(error = e.userMessage(strings, R.string.err_account_request_failed)) }
            } finally {
                _state.update { it.copy(busy = false) }
            }
        }
    }

    fun resend() {
        val current = _state.value
        if (current.busy || current.resendAtMillis > now()) return
        viewModelScope.launch {
            _state.update { it.copy(busy = true, error = null, info = null) }
            try {
                val result = accountRepository.requestVerificationMail()
                if (result.status == "already_verified") {
                    accountRepository.refreshAccount()
                } else {
                    val waitMs = (result.retry_after_seconds ?: 0) * 1000L
                    _state.update {
                        it.copy(
                            delivery = MailDelivery.SENDING,
                            resendAtMillis = if (waitMs > 0) now() + waitMs else 0L,
                            info = strings.get(R.string.verify_email_sent),
                        )
                    }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                val retryAfter = (e as? HttpException)?.takeIf { it.code() == 429 }
                    ?.response()?.headers()?.get("Retry-After")?.toLongOrNull()
                _state.update {
                    it.copy(
                        resendAtMillis = retryAfter?.let { s -> now() + s * 1000 } ?: it.resendAtMillis,
                        error = e.userMessage(strings, R.string.err_account_request_failed),
                    )
                }
            } finally {
                _state.update { it.copy(busy = false) }
            }
        }
    }

    private fun now(): Long = System.currentTimeMillis()
}
