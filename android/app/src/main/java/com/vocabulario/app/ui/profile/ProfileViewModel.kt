package com.vocabulario.app.ui.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.normalizeTenseKey
import com.vocabulario.app.data.normalizeTenseKeys
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ProfileUiState(
    val profiles: List<LanguageProfileResponse> = emptyList(),
    val activeProfile: LanguageProfileResponse? = null,
    val uiLang: String = "pl",
    val selectedTenses: Set<String> = emptySet(),
    val cefrLevel: String = "A2",
    val loading: Boolean = false,
    val error: String? = null,
    val message: String? = null,
)

@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val repository: LearningRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ProfileUiState())
    val state: StateFlow<ProfileUiState> = _state.asStateFlow()

    fun load() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            runCatching {
                val profiles = repository.listProfiles()
                val active = profiles.firstOrNull { it.is_active } ?: profiles.firstOrNull()
                val user = repository.getMe()
                Triple(profiles, active, user.ui_lang)
            }.onSuccess { (profiles, active, uiLang) ->
                _state.value = ProfileUiState(
                    loading = false,
                    profiles = profiles,
                    activeProfile = active,
                    uiLang = uiLang,
                    selectedTenses = normalizeTenseKeys(active?.selected_tenses.orEmpty()).toSet(),
                    cefrLevel = active?.cefr_level ?: "A2",
                )
            }.onFailure {
                _state.value = _state.value.copy(
                    loading = false,
                    error = it.userMessage("Błąd ładowania profilu"),
                )
            }
        }
    }

    fun activateProfile(profileId: String) {
        viewModelScope.launch {
            runCatching { repository.activateProfile(profileId) }
                .onSuccess { load() }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd aktywacji")) }
        }
    }

    fun setCefr(level: String) {
        viewModelScope.launch {
            runCatching { repository.updateProfile(cefr = level) }
                .onSuccess {
                    _state.value = _state.value.copy(cefrLevel = level, message = "Zapisano poziom CEFR")
                    load()
                }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd zapisu")) }
        }
    }

    fun toggleTense(key: String) {
        val current = _state.value.selectedTenses.toMutableSet()
        val canonicalKey = normalizeTenseKey(key)
        if (canonicalKey in current) {
            if (current.size > 1) current.remove(canonicalKey)
        } else {
            current.add(canonicalKey)
        }
        val canonical = normalizeTenseKeys(current)
        viewModelScope.launch {
            runCatching { repository.updateProfile(tenses = canonical) }
                .onSuccess {
                    _state.value = _state.value.copy(
                        selectedTenses = canonical.toSet(),
                        message = "Zapisano czasy",
                    )
                }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd zapisu")) }
        }
    }

    fun setUiLang(lang: String) {
        viewModelScope.launch {
            runCatching { repository.updateUiLang(lang) }
                .onSuccess { _state.value = _state.value.copy(uiLang = lang, message = "Zapisano język UI") }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd zapisu")) }
        }
    }
}
