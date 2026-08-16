package com.vocabulario.app.ui.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.PairSession
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.appLang
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.normalizeTenseKey
import com.vocabulario.app.data.normalizeTenseKeys
import com.vocabulario.app.i18n.AppLocale
import com.vocabulario.app.i18n.UiStrings
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ProfileUiState(
    val profiles: List<LanguageProfileResponse> = emptyList(),
    val activeProfile: LanguageProfileResponse? = null,
    val selectedTenses: Set<String> = emptySet(),
    val cefrLevel: String = "A2",
    val loading: Boolean = false,
    val error: String? = null,
    val message: String? = null,
)

@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val repository: LearningRepository,
    private val tokenStore: TokenStore,
    private val pairSession: PairSession,
    private val strings: UiStrings,
) : ViewModel() {

    private val _state = MutableStateFlow(ProfileUiState())
    val state: StateFlow<ProfileUiState> = _state.asStateFlow()

    fun load() {
        viewModelScope.launch {
            val hadData = _state.value.activeProfile != null
            if (!hadData) {
                _state.value = _state.value.copy(loading = true, error = null)
            }
            runCatching {
                val active = repository.getActiveProfile()
                val profiles = runCatching { repository.listProfiles() }.getOrElse {
                    active?.let { listOf(it) } ?: emptyList()
                }
                val resolvedActive = active
                    ?: profiles.firstOrNull { it.is_active }
                    ?: profiles.firstOrNull()
                profiles to resolvedActive
            }.onSuccess { (profiles, active) ->
                val appLang = active?.appLang ?: "en"
                tokenStore.saveAppLang(appLang)
                AppLocale.apply(appLang)
                _state.value = ProfileUiState(
                    loading = false,
                    profiles = profiles,
                    activeProfile = active,
                    selectedTenses = normalizeTenseKeys(active?.selected_tenses.orEmpty()).toSet(),
                    cefrLevel = active?.cefr_level ?: "A2",
                )
                viewModelScope.launch {
                    runCatching { repository.refreshProfilesFromNetwork() }
                        .onSuccess { remote ->
                            if (remote.isNotEmpty()) {
                                val resolved = remote.firstOrNull { it.is_active } ?: remote.firstOrNull()
                                _state.value = _state.value.copy(
                                    profiles = remote,
                                    activeProfile = resolved ?: _state.value.activeProfile,
                                )
                            }
                        }
                }
            }.onFailure {
                _state.value = _state.value.copy(
                    loading = false,
                    error = it.userMessage(strings, R.string.err_load_profile),
                )
            }
        }
    }

    fun activateProfile(profileId: String) {
        viewModelScope.launch {
            runCatching {
                pairSession.withSwitch(awaitDataReload = true) {
                    val profile = repository.activateProfile(profileId)
                    tokenStore.saveAppLang(profile.appLang)
                    AppLocale.apply(profile.appLang)
                    runCatching { repository.syncNow(fullReplace = true) }
                    profile
                }
            }.onSuccess {
                load()
                pairSession.markDataReady()
            }
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_activate),
                    )
                }
        }
    }

    fun setCefr(level: String) {
        viewModelScope.launch {
            runCatching { repository.updateProfile(cefr = level) }
                .onSuccess {
                    _state.value = _state.value.copy(
                        cefrLevel = level,
                        message = strings.get(R.string.msg_saved_cefr),
                    )
                    load()
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_save),
                    )
                }
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
                        message = strings.get(R.string.msg_saved_tenses),
                    )
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_save),
                    )
                }
        }
    }
}
