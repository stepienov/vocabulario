package com.vocabulario.app.ui.onboarding

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.LanguagePacks
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.deviceUiLang
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.i18n.AppLocale
import com.vocabulario.app.i18n.UiStrings
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

const val LEVEL_UNSURE = "unsure"

data class OnboardingUiState(
    val step: Int = 1,
    val appLang: String = "en",
    val learningLang: String = "",
    val cefrLevel: String = "",
    val loading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class OnboardingViewModel @Inject constructor(
    private val repository: LearningRepository,
    private val tokenStore: TokenStore,
    private val strings: UiStrings,
) : ViewModel() {

    private val _state = MutableStateFlow(OnboardingUiState(appLang = deviceUiLang()))
    val state: StateFlow<OnboardingUiState> = _state.asStateFlow()

    init {
        val lang = _state.value.appLang
        AppLocale.apply(lang)
        viewModelScope.launch { tokenStore.saveAppLang(lang) }
    }

    fun setAppLang(value: String) {
        val current = _state.value
        if (value.equals(current.appLang, ignoreCase = true)) return
        val sameAsLearning = value.equals(current.learningLang, ignoreCase = true)
        _state.value = current.copy(
            appLang = value,
            learningLang = if (sameAsLearning) "" else current.learningLang,
            cefrLevel = if (sameAsLearning) "" else current.cefrLevel,
        )
        AppLocale.apply(value)
        viewModelScope.launch { tokenStore.saveAppLang(value) }
    }

    fun goToLearningStep() {
        _state.value = _state.value.copy(step = 2, error = null)
    }

    fun backToAppLang() {
        _state.value = _state.value.copy(step = 1, error = null)
    }

    fun setLearningLang(value: String) {
        val current = _state.value
        if (value.equals(current.appLang, ignoreCase = true)) {
            _state.value = current.copy(error = strings.get(R.string.err_langs_must_differ))
            return
        }
        _state.value = current.copy(
            learningLang = value,
            cefrLevel = if (value.equals(current.learningLang, ignoreCase = true)) current.cefrLevel else "",
            error = null,
        )
    }

    fun setCefr(value: String) {
        _state.value = _state.value.copy(cefrLevel = value)
    }

    fun complete(onSuccess: () -> Unit) {
        val s = _state.value
        if (s.learningLang.isBlank() || s.cefrLevel.isBlank()) return
        if (s.appLang.equals(s.learningLang, ignoreCase = true)) {
            _state.value = s.copy(error = strings.get(R.string.err_langs_must_differ))
            return
        }
        val cefr = if (s.cefrLevel == LEVEL_UNSURE) "A1" else s.cefrLevel
        val tenses = LanguagePacks.defaultSelectedTenses(s.learningLang)
        viewModelScope.launch {
            _state.value = s.copy(loading = true, error = null)
            runCatching {
                repository.createProfile(
                    appLang = s.appLang,
                    learning = s.learningLang,
                    cefr = cefr,
                    tenses = tenses,
                )
                tokenStore.saveAppLang(s.appLang)
                AppLocale.apply(s.appLang)
            }.onSuccess { onSuccess() }
                .onFailure {
                    _state.value = _state.value.copy(
                        loading = false,
                        error = it.userMessage(strings, R.string.err_create_profile),
                    )
                }
        }
    }
}
