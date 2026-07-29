package com.vocabulario.app.ui.onboarding

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.userMessage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class OnboardingUiState(
    val nativeLang: String = "pl",
    val learningLang: String = "es",
    val cefrLevel: String = "A2",
    val selectedTenses: Set<String> = setOf("presente", "preterito_indefinido", "preterito_imperfecto"),
    val loading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class OnboardingViewModel @Inject constructor(
    private val repository: LearningRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(OnboardingUiState())
    val state: StateFlow<OnboardingUiState> = _state.asStateFlow()

    fun setNativeLang(value: String) {
        _state.value = _state.value.copy(nativeLang = value)
    }

    fun setLearningLang(value: String) {
        _state.value = _state.value.copy(learningLang = value)
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
        if (s.nativeLang == s.learningLang) {
            _state.value = s.copy(error = "Język ojczysty i uczony muszą być różne")
            return
        }
        viewModelScope.launch {
            _state.value = s.copy(loading = true, error = null)
            runCatching {
                repository.createProfile(
                    native = s.nativeLang,
                    learning = s.learningLang,
                    cefr = s.cefrLevel,
                    tenses = s.selectedTenses.toList(),
                )
            }.onSuccess { onSuccess() }
                .onFailure {
                    _state.value = _state.value.copy(
                        loading = false,
                        error = it.userMessage("Błąd tworzenia profilu"),
                    )
                }
        }
    }
}
