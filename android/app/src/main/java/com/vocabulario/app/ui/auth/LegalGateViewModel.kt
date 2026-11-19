package com.vocabulario.app.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.LegalRepository
import com.vocabulario.app.data.api.legalManifestFromError
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

data class LegalGateUiState(
    val consent: LegalConsentState = LegalConsentState(),
    val busy: Boolean = false,
    val error: String? = null,
)

/**
 * Bramka nowej wersji warunków (F-007/T-003). Bez pollingu: manifest czytany raz przy wejściu
 * i na ponowienie; po zaakceptowaniu [com.vocabulario.app.data.LegalGate] zdejmuje bramkę.
 */
@HiltViewModel
class LegalGateViewModel @Inject constructor(
    private val legalRepository: LegalRepository,
    private val strings: UiStrings,
) : ViewModel() {

    private val _state = MutableStateFlow(LegalGateUiState())
    val state: StateFlow<LegalGateUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        val current = _state.value.consent
        if (current.loading || current.manifest != null) return
        viewModelScope.launch {
            _state.update { it.copy(consent = it.consent.copy(loading = true, loadFailed = false)) }
            try {
                val manifest = legalRepository.manifest()
                _state.update { it.copy(consent = it.consent.copy(manifest = manifest, loading = false)) }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                _state.update { it.copy(consent = it.consent.copy(loading = false, loadFailed = true)) }
            }
        }
    }

    fun setTermsAccepted(value: Boolean) =
        _state.update { it.copy(consent = it.consent.copy(termsAccepted = value), error = null) }

    fun setAdultConfirmed(value: Boolean) =
        _state.update { it.copy(consent = it.consent.copy(adultConfirmed = value), error = null) }

    fun accept() {
        val current = _state.value
        val manifest = current.consent.manifest ?: return
        if (current.busy || !current.consent.termsAccepted || !current.consent.adultConfirmed) return
        viewModelScope.launch {
            _state.update { it.copy(busy = true, error = null) }
            try {
                legalRepository.accept(manifest)
                _state.update { it.copy(busy = false) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                val fresh = e.legalManifestFromError()
                _state.update {
                    it.copy(
                        busy = false,
                        consent = if (fresh != null) {
                            it.consent.copy(manifest = fresh, termsAccepted = false)
                        } else {
                            it.consent
                        },
                        error = e.userMessage(strings, R.string.err_account_request_failed),
                    )
                }
            }
        }
    }
}
