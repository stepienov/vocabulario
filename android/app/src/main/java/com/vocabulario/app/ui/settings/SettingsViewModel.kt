package com.vocabulario.app.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
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
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
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
    val reminderMinute: Int = 0,
) {
    val notificationsEnabled: Boolean get() = studyReminderEnabled || cardsReadyPushEnabled
}

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val repository: LearningRepository,
    private val tokenStore: TokenStore,
    private val strings: UiStrings,
    private val notificationScheduler: com.vocabulario.app.notifications.NotificationScheduler,
    private val pairSession: PairSession,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()
    private var reminderSaveJob: Job? = null
    private var limitsSaveJob: Job? = null
    private var cefrSaveJob: Job? = null
    /** Kolejne tapnięcia / load() nie mogą stosować starszego snapshota. */
    private var writeGen = 0
    private var inFlightSaves = 0

    init {
        if (tokenStore.consumeExpandLanguages()) {
            _state.value = _state.value.copy(expanded = SettingsSection.LANGUAGES)
        }
        // Reaktywnie: zmiana ustawień w Room (lokalna lub dociągnięta z sync) aktualizuje UI.
        viewModelScope.launch {
            repository.observeSettings().collect { s ->
                if (s == null) return@collect
                if (inFlightSaves > 0 ||
                    reminderSaveJob?.isActive == true ||
                    limitsSaveJob?.isActive == true
                ) return@collect
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
                    reminderMinute = notificationScheduler.reminderMinute(),
                )
            }
        }
    }

    fun load() {
        viewModelScope.launch {
            val genAtStart = writeGen
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
                resolvedActive?.let { tokenStore.saveActiveProfile(it.id) }
                AppLocale.applyIfChanged(
                    resolvedActive?.appLang ?: tokenStore.peekAppLang().ifBlank { "en" },
                )
                Triple(settings, profiles, resolvedActive)
            }.onSuccess { (_, profilesIn, _) ->
                if (writeGen != genAtStart) {
                    _state.value = _state.value.copy(loading = false)
                    return@onSuccess
                }
                val s = repository.getSettings()
                val active = repository.getActiveProfile()
                    ?: profilesIn.firstOrNull { it.is_active }
                    ?: profilesIn.firstOrNull()
                val profiles = repository.listProfiles().ifEmpty { profilesIn }
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
                    reminderMinute = notificationScheduler.reminderMinute(),
                )
                notificationScheduler.scheduleStudyReminder(
                    s.reminder_hour,
                    s.study_reminder_enabled || s.cards_ready_push_enabled,
                    notificationScheduler.reminderMinute(),
                )
                viewModelScope.launch {
                    runCatching { repository.refreshProfilesFromNetwork() }
                        .onSuccess { remote ->
                            if (remote.isEmpty()) return@onSuccess
                            if (writeGen != genAtStart) {
                                _state.value = _state.value.copy(profiles = remote)
                                return@onSuccess
                            }
                            val resolved = repository.getActiveProfile()
                                ?: remote.firstOrNull { it.is_active }
                                ?: remote.firstOrNull()
                            resolved?.let { tokenStore.saveActiveProfile(it.id) }
                            _state.value = _state.value.copy(
                                profiles = remote,
                                activeProfile = resolved ?: _state.value.activeProfile,
                            )
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
        val previous = _state.value
        val gen = ++writeGen
        _state.value = onUpdated(previous).copy(error = null)
        viewModelScope.launch {
            inFlightSaves++
            update.theme?.let { tokenStore.saveTheme(it) }
            runCatching { repository.updateSettings(update) }
                .onSuccess { result ->
                    if (writeGen != gen) return@onSuccess
                    result.theme.let { tokenStore.saveTheme(it) }
                    _state.value = _state.value.copy(theme = result.theme, error = null)
                }
                .onFailure {
                    if (writeGen != gen) return@onFailure
                    _state.value = previous.copy(
                        error = it.userMessage(strings, R.string.err_save),
                    )
                    previous.theme.let { theme ->
                        runCatching { tokenStore.saveTheme(theme) }
                    }
                }
            inFlightSaves--
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
        val clamped = value.coerceIn(5, 50)
        if (_state.value.newCardsPerDay == clamped) return
        writeGen++
        _state.value = _state.value.copy(newCardsPerDay = clamped, error = null)
        limitsSaveJob?.cancel()
        limitsSaveJob = viewModelScope.launch {
            delay(400)
            save(UserSettingsUpdate(new_cards_per_day = clamped)) { it.copy(newCardsPerDay = clamped) }
        }
    }

    fun setTheme(value: String) =
        save(UserSettingsUpdate(theme = value)) { it.copy(theme = value) }

    fun setNotificationsEnabled(value: Boolean) {
        save(
            UserSettingsUpdate(
                study_reminder_enabled = value,
                cards_ready_push_enabled = value,
            ),
        ) {
            notificationScheduler.scheduleStudyReminder(it.reminderHour, value, it.reminderMinute)
            it.copy(studyReminderEnabled = value, cardsReadyPushEnabled = value)
        }
    }

    fun setReminderHour(hour: Int) {
        setReminderTime(hour, _state.value.reminderMinute)
    }

    fun setReminderMinute(minute: Int) {
        setReminderTime(_state.value.reminderHour, minute)
    }

    fun setReminderTime(hour: Int, minute: Int) {
        val safeHour = hour.coerceIn(0, 23)
        val safeMinute = minute.coerceIn(0, 59)
        writeGen++
        _state.value = _state.value.copy(reminderHour = safeHour, reminderMinute = safeMinute)
        notificationScheduler.scheduleStudyReminder(
            safeHour,
            _state.value.notificationsEnabled,
            safeMinute,
        )
        reminderSaveJob?.cancel()
        reminderSaveJob = viewModelScope.launch {
            delay(450)
            save(UserSettingsUpdate(reminder_hour = safeHour)) {
                it.copy(reminderHour = safeHour, reminderMinute = safeMinute)
            }
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
        val previous = _state.value
        val gen = ++writeGen
        _state.value = previous.copy(
            selectedTenses = canonical,
            lastCustomTenses = if (rememberCustom && canonical.isNotEmpty()) {
                canonical
            } else {
                previous.lastCustomTenses
            },
            showConjugation = conjugationOn,
            error = null,
        )
        viewModelScope.launch {
            runCatching {
                val profile = repository.updateProfile(tenses = canonical.toList())
                repository.updateSettings(UserSettingsUpdate(show_conjugation = conjugationOn))
                profile
            }.onSuccess { profile ->
                if (writeGen != gen) return@onSuccess
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
                if (writeGen != gen) return@onFailure
                _state.value = previous.copy(
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
        switchLangPair(appLang = code, learningLang = current.learning_lang, cefr = current.cefr_level)
    }

    fun setLearningLang(code: String) {
        val current = _state.value.activeProfile ?: return
        if (current.learning_lang.equals(code, ignoreCase = true)) return
        if (code.equals(current.appLang, ignoreCase = true)) {
            _state.value = _state.value.copy(error = strings.get(R.string.err_langs_must_differ))
            return
        }
        switchLangPair(appLang = current.appLang, learningLang = code, cefr = current.cefr_level)
    }

    private fun switchLangPair(appLang: String, learningLang: String, cefr: String) {
        val previous = _state.value.activeProfile
        cefrSaveJob?.cancel()
        tokenStore.markReopenSettings()
        _state.value = _state.value.copy(error = null, expanded = SettingsSection.LANGUAGES)
        viewModelScope.launch {
            runCatching {
                pairSession.withSwitch(awaitDataReload = true) {
                    val profile = repository.switchToLangPair(
                        appLang = appLang,
                        learningLang = learningLang,
                        cefr = cefr,
                    )
                    runCatching { repository.syncNow(fullReplace = true) }
                    AppLocale.applyIfChanged(profile.appLang)
                    profile
                }
            }.onSuccess { profile ->
                _state.value = _state.value.copy(
                    activeProfile = profile,
                    cefrLevel = profile.cefr_level,
                    profiles = runCatching { repository.listProfiles() }.getOrElse { _state.value.profiles },
                    expanded = SettingsSection.LANGUAGES,
                    error = null,
                )
                pairSession.markDataReady()
            }.onFailure { err ->
                if (err is CancellationException) throw err
                _state.value = _state.value.copy(
                    activeProfile = previous,
                    error = err.userMessage(strings, R.string.err_learning_lang),
                    expanded = SettingsSection.LANGUAGES,
                )
                pairSession.markDataReady()
            }
        }
    }

    fun setCefr(level: String) {
        if (_state.value.cefrLevel == level) return
        _state.value = _state.value.copy(cefrLevel = level, error = null)
        cefrSaveJob?.cancel()
        cefrSaveJob = viewModelScope.launch {
            try {
                val profile = repository.updateProfile(cefr = level)
                _state.value = _state.value.copy(
                    cefrLevel = level,
                    activeProfile = profile,
                    error = null,
                )
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    error = e.userMessage(strings, R.string.err_cefr),
                )
            }
        }
    }
}
