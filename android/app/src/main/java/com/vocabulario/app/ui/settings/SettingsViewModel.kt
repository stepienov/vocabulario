package com.vocabulario.app.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.LanguagePacks
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.PairSession
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.appLang
import com.vocabulario.app.data.api.UserSettingsUpdate
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.normalizeTenseKeys
import com.vocabulario.app.i18n.AppLocale
import com.vocabulario.app.i18n.UiStrings
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
    NOTIFICATIONS,
}

data class SettingsUiState(
    val expanded: SettingsSection = SettingsSection.NONE,
    val practiceInputPref: String = "flashcard",
    val practiceDirection: String = "l2_to_l1",
    val typingTolerance: String = "tolerate",
    val newCardsPerDay: Int = 20,
    val theme: String = "system",
    val showExampleSentences: Boolean = true,
    val showUsages: Boolean = true,
    val showSynonyms: Boolean = true,
    val showAntonyms: Boolean = true,
    val showWordFamily: Boolean = true,
    val showPeriphrases: Boolean = true,
    val showConjugation: Boolean = true,
    /** Aktywne czasy w profilu; puste = tryb „wszystkie czasy”. */
    val selectedTenses: Set<String> = emptySet(),
    /** Ostatni własny wybór — zachowany przy „wszystkie” / wyłączeniu koniugacji. */
    val lastCustomTenses: Set<String> = emptySet(),
    val tenseLabelLang: String = "app_lang",
    val profiles: List<LanguageProfileResponse> = emptyList(),
    val activeProfile: LanguageProfileResponse? = null,
    val cefrLevel: String = "A2",
    val loading: Boolean = false,
    val error: String? = null,
    val studyReminderEnabled: Boolean = true,
    val cardsReadyPushEnabled: Boolean = true,
    val reminderHour: Int = 19,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val repository: LearningRepository,
    private val tokenStore: TokenStore,
    private val pairSession: PairSession,
    private val strings: UiStrings,
    private val notificationScheduler: com.vocabulario.app.notifications.NotificationScheduler,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        // Reaktywnie: zmiana ustawień w Room (lokalna lub dociągnięta z sync) aktualizuje UI.
        viewModelScope.launch {
            repository.observeSettings().collect { s ->
                if (s == null) return@collect
                val showSyn = if (s.show_synonyms_antonyms) s.show_synonyms else false
                val showAnt = if (s.show_synonyms_antonyms) s.show_antonyms else false
                _state.value = _state.value.copy(
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
                    showWordFamily = s.show_word_family,
                    showPeriphrases = s.show_periphrases,
                    showConjugation = s.show_conjugation,
                    studyReminderEnabled = s.study_reminder_enabled,
                    cardsReadyPushEnabled = s.cards_ready_push_enabled,
                    reminderHour = s.reminder_hour,
                )
            }
        }
    }

    fun load() {
        viewModelScope.launch {
            val hadData = _state.value.activeProfile != null
            if (!hadData) {
                _state.value = _state.value.copy(loading = true, error = null)
            }
            runCatching {
                val settings = repository.getSettings()
                val active = repository.getActiveProfile()
                val profiles = runCatching { repository.listProfiles() }.getOrElse {
                    active?.let { listOf(it) } ?: emptyList()
                }
                val resolvedActive = active
                    ?: profiles.firstOrNull { it.is_active }
                    ?: profiles.firstOrNull()
                Triple(settings, profiles, resolvedActive)
            }.onSuccess { (s, profiles, active) ->
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
                    showWordFamily = s.show_word_family,
                    showPeriphrases = s.show_periphrases,
                    showConjugation = s.show_conjugation,
                    selectedTenses = selected,
                    lastCustomTenses = selected.ifEmpty { _state.value.lastCustomTenses },
                    tenseLabelLang = active?.tense_label_lang ?: "app_lang",
                    profiles = profiles,
                    activeProfile = active,
                    cefrLevel = active?.cefr_level ?: "A2",
                    studyReminderEnabled = s.study_reminder_enabled,
                    cardsReadyPushEnabled = s.cards_ready_push_enabled,
                    reminderHour = s.reminder_hour,
                )
                notificationScheduler.scheduleStudyReminder(s.reminder_hour, s.study_reminder_enabled)
                active?.let {
                    tokenStore.saveActiveProfile(it.id)
                    tokenStore.saveAppLang(it.appLang)
                    AppLocale.apply(it.appLang)
                }
                viewModelScope.launch {
                    runCatching { repository.refreshProfilesFromNetwork() }
                        .onSuccess { remote ->
                            if (remote.isNotEmpty()) {
                                _state.value = _state.value.copy(profiles = remote)
                            }
                        }
                }
            }.onFailure {
                _state.value = _state.value.copy(
                    loading = false,
                    error = it.userMessage(strings, R.string.err_load_settings),
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
        // Optimistic UI — radio/toggles respond immediately; revert on failure.
        val previous = _state.value
        _state.value = onUpdated(previous).copy(error = null)
        viewModelScope.launch {
            update.theme?.let { tokenStore.saveTheme(it) }
            runCatching { repository.updateSettings(update) }
                .onSuccess { result ->
                    result.theme.let { tokenStore.saveTheme(it) }
                    _state.value = onUpdated(_state.value).copy(
                        theme = result.theme,
                        error = null,
                    )
                }
                .onFailure {
                    _state.value = previous.copy(
                        error = it.userMessage(strings, R.string.err_save),
                    )
                    previous.theme.let { theme ->
                        runCatching { tokenStore.saveTheme(theme) }
                    }
                }
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

    fun setStudyReminderEnabled(value: Boolean) {
        save(UserSettingsUpdate(study_reminder_enabled = value)) {
            notificationScheduler.scheduleStudyReminder(it.reminderHour, value)
            it.copy(studyReminderEnabled = value)
        }
    }

    fun setCardsReadyPushEnabled(value: Boolean) =
        save(UserSettingsUpdate(cards_ready_push_enabled = value)) { it.copy(cardsReadyPushEnabled = value) }

    fun setReminderHour(value: Int) {
        val hour = value.coerceIn(0, 23)
        save(UserSettingsUpdate(reminder_hour = hour)) {
            notificationScheduler.scheduleStudyReminder(hour, it.studyReminderEnabled)
            it.copy(reminderHour = hour)
        }
    }

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

    fun setShowWordFamily(value: Boolean) =
        save(UserSettingsUpdate(show_word_family = value)) { it.copy(showWordFamily = value) }

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
            }.onFailure {
                _state.value = _state.value.copy(
                    error = it.userMessage(strings, R.string.err_save_tenses),
                )
            }
        }
    }

    fun setAppLang(code: String) {
        val current = _state.value.activeProfile ?: return
        if (current.appLang.equals(code, ignoreCase = true)) return
        if (code.equals(current.learning_lang, ignoreCase = true)) {
            _state.value = _state.value.copy(error = strings.get(R.string.err_langs_must_differ))
            return
        }
        switchOrCreateProfile(appLang = code, learning = current.learning_lang, cefr = current.cefr_level)
    }

    fun setLearningLang(code: String) {
        val current = _state.value.activeProfile ?: return
        if (current.learning_lang.equals(code, ignoreCase = true)) return
        if (code.equals(current.appLang, ignoreCase = true)) {
            _state.value = _state.value.copy(error = strings.get(R.string.err_langs_must_differ))
            return
        }
        switchOrCreateProfile(appLang = current.appLang, learning = code, cefr = current.cefr_level)
    }

    fun setTenseLabelLang(value: String) {
        if (value != "app_lang" && value != "learning_lang") return
        val current = _state.value.activeProfile ?: return
        if (current.tense_label_lang == value) return
        viewModelScope.launch {
            runCatching { repository.updateProfile(tenseLabelLang = value) }
                .onSuccess { profile ->
                    _state.value = _state.value.copy(activeProfile = profile, tenseLabelLang = value)
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_save),
                    )
                }
        }
    }

    private fun switchOrCreateProfile(appLang: String, learning: String, cefr: String) {
        viewModelScope.launch {
            runCatching {
                pairSession.withSwitch(awaitDataReload = true) {
                    val existing = _state.value.profiles.firstOrNull {
                        it.appLang.equals(appLang, true) && it.learning_lang.equals(learning, true)
                    }
                    if (existing != null) {
                        repository.activateProfile(existing.id)
                    } else {
                        repository.createProfile(
                            appLang = appLang,
                            learning = learning,
                            cefr = cefr,
                            tenses = LanguagePacks.defaultSelectedTenses(learning),
                        )
                    }
                    tokenStore.saveAppLang(appLang)
                    AppLocale.apply(appLang)
                    runCatching { repository.syncNow(fullReplace = true) }
                }
            }.onSuccess {
                load()
                pairSession.markDataReady()
                _state.value = _state.value.copy(expanded = SettingsSection.LANGUAGES)
            }.onFailure {
                _state.value = _state.value.copy(
                    error = it.userMessage(strings, R.string.err_learning_lang),
                )
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
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_cefr),
                    )
                }
        }
    }
}
