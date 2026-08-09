package com.vocabulario.app.ui.onboarding

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.LanguagePacks
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.i18n.AppLocale
import com.vocabulario.app.i18n.UiStrings
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class OnboardingUiState(
    val appLang: String = "en",
    val learningLang: String = "es",
    val cefrLevel: String = "A2",
    val selectedTenses: Set<String> = LanguagePacks.defaultSelectedTenses("es").toSet(),
    val loading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class OnboardingViewModel @Inject constructor(
    private val repository: LearningRepository,
    private val tokenStore: TokenStore,
    private val strings: UiStrings,
) : ViewModel() {

    private val _state = MutableStateFlow(OnboardingUiState())
    val state: StateFlow<OnboardingUiState> = _state.asStateFlow()

    fun setAppLang(value: String) {
        _state.value = _state.value.copy(appLang = value)
    }

    fun setLearningLang(value: String) {
        val defaults = LanguagePacks.defaultSelectedTenses(value).toSet()
        _state.value = _state.value.copy(
            learningLang = value,
            selectedTenses = if (LanguagePacks.showsTensePicker(value)) {
                defaults.ifEmpty { _state.value.selectedTenses }
            } else {
                emptySet()
            },
        )
    }

    fun setCefr(value: String) {
        _state.value = _state.value.copy(cefrLevel = value)
    }

    fun toggleTense(key: String) {
        val current = _state.value.selectedTenses.toMutableSet()
        if (key in current) {
            if (current.size > 1) current.remove(key)
        } else {
            current.add(key)
        }
        _state.value = _state.value.copy(selectedTenses = current)
    }

    fun complete(onSuccess: () -> Unit) {
        val s = _state.value
        if (s.appLang == s.learningLang) {
            _state.value = s.copy(error = strings.get(R.string.err_langs_must_differ))
            return
        }
        viewModelScope.launch {
            _state.value = s.copy(loading = true, error = null)
            runCatching {
                repository.createProfile(
                    appLang = s.appLang,
                    learning = s.learningLang,
                    cefr = s.cefrLevel,
                    tenses = s.selectedTenses.toList(),
                )
                tokenStore.saveAppLang(s.appLang)
                AppLocale.apply(s.appLang)
            }.onSuccess { onSuccess() }
                .onFailure {
                    _state.value = _state.value.copy(
                        loading = false,
                        error = it.userMessage(strings.get(R.string.err_create_profile)),
                    )
                }
        }
    }
}
