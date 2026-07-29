package com.vocabulario.app.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.UserSettingsUpdate
import com.vocabulario.app.data.api.userMessage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val practiceInputPref: String = "choice",
    val practiceDirection: String = "l2_to_l1",
    val newCardsPerDay: Int = 20,
    val theme: String = "system",
    val showUsages: Boolean = true,
    val showExampleSentences: Boolean = true,
    val showSynonymsAntonyms: Boolean = true,
    val showPeriphrases: Boolean = true,
    val conjugationExpandedDefault: Boolean = false,
    val relatedWordsExpandedDefault: Boolean = false,
    val activeProfile: LanguageProfileResponse? = null,
    val loading: Boolean = false,
    val error: String? = null,
    val message: String? = null,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val repository: LearningRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    fun load() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            runCatching {
                val settings = repository.getSettings()
                val profile = repository.getActiveProfile()
                settings to profile
            }.onSuccess { (s, profile) ->
                _state.value = SettingsUiState(
                    loading = false,
                    practiceInputPref = when (s.practice_input_pref) {
                        "random" -> "choice"
                        else -> s.practice_input_pref
                    },
                    practiceDirection = s.practice_direction,
                    newCardsPerDay = s.new_cards_per_day,
                    theme = s.theme,
                    showUsages = s.show_usages,
                    showExampleSentences = s.show_example_sentences,
                    showSynonymsAntonyms = s.show_synonyms_antonyms,
                    showPeriphrases = s.show_periphrases,
                    conjugationExpandedDefault = s.conjugation_expanded_default,
                    relatedWordsExpandedDefault = s.related_words_expanded_default,
                    activeProfile = profile,
                )
            }.onFailure {
                _state.value = _state.value.copy(
                    loading = false,
                    error = it.userMessage("Błąd ładowania ustawień"),
                )
            }
        }
    }

    private fun save(update: UserSettingsUpdate, onUpdated: (SettingsUiState) -> SettingsUiState) {
        viewModelScope.launch {
            runCatching { repository.updateSettings(update) }
                .onSuccess { _state.value = onUpdated(_state.value).copy(message = "Zapisano") }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd zapisu")) }
        }
    }

    fun setInputPref(value: String) = save(UserSettingsUpdate(practice_input_pref = value)) { it.copy(practiceInputPref = value) }
    fun setDirection(value: String) = save(UserSettingsUpdate(practice_direction = value)) { it.copy(practiceDirection = value) }
    fun setNewCardsPerDay(value: Int) = save(UserSettingsUpdate(new_cards_per_day = value)) { it.copy(newCardsPerDay = value) }
    fun setTheme(value: String) = save(UserSettingsUpdate(theme = value)) { it.copy(theme = value) }
    fun setShowUsages(value: Boolean) = save(UserSettingsUpdate(show_usages = value)) { it.copy(showUsages = value) }
    fun setShowExampleSentences(value: Boolean) = save(UserSettingsUpdate(show_example_sentences = value)) { it.copy(showExampleSentences = value) }
    fun setShowSynonymsAntonyms(value: Boolean) = save(UserSettingsUpdate(show_synonyms_antonyms = value)) { it.copy(showSynonymsAntonyms = value) }
    fun setShowPeriphrases(value: Boolean) = save(UserSettingsUpdate(show_periphrases = value)) { it.copy(showPeriphrases = value) }
    fun setConjugationExpandedDefault(value: Boolean) = save(UserSettingsUpdate(conjugation_expanded_default = value)) { it.copy(conjugationExpandedDefault = value) }
    fun setRelatedWordsExpandedDefault(value: Boolean) = save(UserSettingsUpdate(related_words_expanded_default = value)) { it.copy(relatedWordsExpandedDefault = value) }
}
