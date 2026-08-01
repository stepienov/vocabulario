package com.vocabulario.app.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.UserSettingsUpdate
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.normalizeTenseKeys
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

enum class SettingsSection {
    NONE,
    MODE,
    DIRECTION,
    CARD_LAYOUT,
    LIMITS,
    THEME,
    LANGUAGES,
    CEFR,
}

data class SettingsUiState(
    val expanded: SettingsSection = SettingsSection.NONE,
    val practiceInputPref: String = "choice",
    val practiceDirection: String = "l2_to_l1",
    val typingTolerance: String = "tolerate",
    val newCardsPerDay: Int = 20,
    val theme: String = "system",
    val showExampleSentences: Boolean = true,
    val showUsages: Boolean = true,
    val showSynonyms: Boolean = true,
    val showAntonyms: Boolean = true,
    val showPeriphrases: Boolean = true,
    val showConjugation: Boolean = true,
    /** Aktywne czasy w profilu; puste = tryb „wszystkie czasy”. */
    val selectedTenses: Set<String> = emptySet(),
    /** Ostatni własny wybór — zachowany przy „wszystkie” / wyłączeniu koniugacji. */
    val lastCustomTenses: Set<String> = emptySet(),
    val uiLang: String = "pl",
    val profiles: List<LanguageProfileResponse> = emptyList(),
    val activeProfile: LanguageProfileResponse? = null,
    val cefrLevel: String = "A2",
    val loading: Boolean = false,
    val error: String? = null,
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
                val profiles = repository.listProfiles()
                val me = runCatching { repository.getMe() }.getOrNull()
                val active = profiles.firstOrNull { it.is_active } ?: profiles.firstOrNull()
                Triple(settings, profiles to active, me)
            }.onSuccess { (s, profilesPair, me) ->
                val (profiles, active) = profilesPair
                val showSyn = if (s.show_synonyms_antonyms) s.show_synonyms else false
                val showAnt = if (s.show_synonyms_antonyms) s.show_antonyms else false
                val selected = normalizeTenseKeys(active?.selected_tenses.orEmpty()).toSet()
                _state.value = SettingsUiState(
                    loading = false,
                    expanded = _state.value.expanded,
                    practiceInputPref = when (s.practice_input_pref) {
                        "random" -> "choice"
                        else -> s.practice_input_pref
                    },
                    practiceDirection = s.practice_direction,
                    typingTolerance = s.typing_tolerance,
                    newCardsPerDay = s.new_cards_per_day,
                    theme = s.theme,
                    showExampleSentences = s.show_example_sentences,
                    showUsages = s.show_usages,
                    showSynonyms = showSyn,
                    showAntonyms = showAnt,
                    showPeriphrases = s.show_periphrases,
                    showConjugation = s.show_conjugation,
                    selectedTenses = selected,
                    lastCustomTenses = selected.ifEmpty { _state.value.lastCustomTenses },
                    uiLang = me?.ui_lang ?: "pl",
                    profiles = profiles,
                    activeProfile = active,
                    cefrLevel = active?.cefr_level ?: "A2",
                )
            }.onFailure {
                _state.value = _state.value.copy(
                    loading = false,
                    error = it.userMessage("Błąd ładowania ustawień"),
                )
            }
        }
    }

    fun toggleSection(section: SettingsSection) {
        _state.value = _state.value.copy(
            expanded = if (_state.value.expanded == section) SettingsSection.NONE else section,
        )
    }

    private fun save(update: UserSettingsUpdate, onUpdated: (SettingsUiState) -> SettingsUiState) {
        viewModelScope.launch {
            runCatching { repository.updateSettings(update) }
                .onSuccess { _state.value = onUpdated(_state.value).copy(error = null) }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd zapisu")) }
        }
    }

    fun setInputPref(value: String) =
        save(UserSettingsUpdate(practice_input_pref = value)) { it.copy(practiceInputPref = value) }

    fun setTypingTolerance(tolerate: Boolean) {
        val value = if (tolerate) "tolerate" else "strict"
        save(UserSettingsUpdate(typing_tolerance = value)) { it.copy(typingTolerance = value) }
    }

    fun setDirection(value: String) =
        save(UserSettingsUpdate(practice_direction = value)) { it.copy(practiceDirection = value) }

    fun setNewCardsPerDay(value: Int) {
        val clamped = value.coerceIn(1, 200)
        save(UserSettingsUpdate(new_cards_per_day = clamped)) { it.copy(newCardsPerDay = clamped) }
    }

    fun setTheme(value: String) =
        save(UserSettingsUpdate(theme = value)) { it.copy(theme = value) }

    fun setShowExampleSentences(value: Boolean) =
        save(UserSettingsUpdate(show_example_sentences = value)) { it.copy(showExampleSentences = value) }

    fun setShowUsages(value: Boolean) =
        save(UserSettingsUpdate(show_usages = value)) { it.copy(showUsages = value) }

    fun setShowSynonymsAndAntonyms(value: Boolean) {
        save(
            UserSettingsUpdate(
                show_synonyms = value,
                show_antonyms = value,
                show_synonyms_antonyms = value,
            ),
        ) { it.copy(showSynonyms = value, showAntonyms = value) }
    }

    fun setShowPeriphrases(value: Boolean) =
        save(UserSettingsUpdate(show_periphrases = value)) { it.copy(showPeriphrases = value) }

    /** Włącza/wyłącza koniugację; nie czyści wybranych czasów. */
    fun setShowConjugation(value: Boolean) {
        save(UserSettingsUpdate(show_conjugation = value)) { it.copy(showConjugation = value) }
    }

    /** Pusta lista w profilu = wszystkie czasy; lastCustom zostaje. */
    fun setAllTenses() {
        val current = _state.value.selectedTenses
        if (current.isNotEmpty()) {
            _state.value = _state.value.copy(lastCustomTenses = current)
        }
        persistTenses(emptySet(), conjugationOn = true, rememberCustom = false)
    }

    /**
     * Przywraca ostatni własny wybór.
     * @return true gdy trzeba otworzyć modal (nie ma jeszcze zapamiętanych czasów).
     */
    fun selectCustomTenses(): Boolean {
        val last = _state.value.lastCustomTenses
        if (last.isEmpty()) return true
        if (_state.value.selectedTenses == last) return false
        persistTenses(last, conjugationOn = true, rememberCustom = true)
        return false
    }

    fun setCustomTenses(tenses: Set<String>) {
        val canonical = normalizeTenseKeys(tenses).toSet()
        if (canonical.isEmpty()) return // puste zatwierdzenie = no-op (UI cofa stan)
        persistTenses(canonical, conjugationOn = true, rememberCustom = true)
    }

    private fun persistTenses(
        tenses: Set<String>,
        conjugationOn: Boolean,
        rememberCustom: Boolean,
    ) {
        val canonical = normalizeTenseKeys(tenses).toSet()
        viewModelScope.launch {
            runCatching {
                val profile = repository.updateProfile(tenses = canonical.toList())
                repository.updateSettings(UserSettingsUpdate(show_conjugation = conjugationOn))
                profile
            }.onSuccess { profile ->
                _state.value = _state.value.copy(
                    selectedTenses = canonical,
                    lastCustomTenses = if (rememberCustom && canonical.isNotEmpty()) {
                        canonical
                    } else {
                        _state.value.lastCustomTenses
                    },
                    activeProfile = profile,
                    showConjugation = conjugationOn,
                )
            }.onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd zapisu czasów")) }
        }
    }

    fun setUiLang(code: String) {
        viewModelScope.launch {
            runCatching { repository.updateUiLang(code) }
                .onSuccess { _state.value = _state.value.copy(uiLang = code) }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd języka UI")) }
        }
    }

    fun setLearningLang(code: String) {
        val current = _state.value.activeProfile ?: return
        if (current.learning_lang.equals(code, ignoreCase = true)) return
        viewModelScope.launch {
            runCatching {
                val existing = _state.value.profiles.firstOrNull {
                    it.native_lang.equals(current.native_lang, true) &&
                        it.learning_lang.equals(code, true)
                }
                if (existing != null) {
                    repository.activateProfile(existing.id)
                } else {
                    repository.createProfile(
                        native = current.native_lang,
                        learning = code,
                        cefr = current.cefr_level,
                        tenses = current.selected_tenses,
                    )
                }
            }.onSuccess {
                load()
                _state.value = _state.value.copy(expanded = SettingsSection.LANGUAGES)
            }.onFailure {
                _state.value = _state.value.copy(error = it.userMessage("Błąd zmiany języka nauki"))
            }
        }
    }

    fun setCefr(level: String) {
        viewModelScope.launch {
            runCatching { repository.updateProfile(cefr = level) }
                .onSuccess { profile ->
                    _state.value = _state.value.copy(
                        cefrLevel = level,
                        activeProfile = profile,
                    )
                }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd CEFR")) }
        }
    }
}
