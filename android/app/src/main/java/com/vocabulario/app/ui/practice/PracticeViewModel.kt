package com.vocabulario.app.ui.practice

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.ChoiceOption
import com.vocabulario.app.data.api.SrsQueueItem
import com.vocabulario.app.data.api.SyncSrsState
import com.vocabulario.app.data.api.WordListResponse
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.normalizeTenseKeys
import com.vocabulario.app.i18n.UiStrings
import com.vocabulario.app.ui.card.RelatedWord
import com.vocabulario.app.ui.home.listNameConflictMessage
import com.vocabulario.app.ui.card.CorrectionResultItem
import com.vocabulario.app.ui.card.CorrectionResultsState
import com.vocabulario.app.ui.card.HomeUiStateSelfEditActive
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.json.buildJsonObject
import javax.inject.Inject

enum class PracticePhase {
    ANSWERING,
    WRONG_MODAL,
    SHOW_CARD,
}

enum class AnswerMode {
    CHOICE,
    TYPE,
    FLASHCARD,
}

data class UndoFrame(
    val clientId: String,
    val cardId: String,
    val previousIndex: Int,
    val previousPhase: PracticePhase,
    val previousAnswerMode: AnswerMode,
    val previousTypedAnswer: String,
    val previousLastCorrect: Boolean?,
    val snapshot: SyncSrsState,
    val wasSessionComplete: Boolean,
)

data class PracticeUiState(
    val loading: Boolean = false,
    val grading: Boolean = false,
    val queue: List<SrsQueueItem> = emptyList(),
    val currentIndex: Int = 0,
    val phase: PracticePhase = PracticePhase.ANSWERING,
    val answerMode: AnswerMode = AnswerMode.CHOICE,
    val choices: List<ChoiceOption> = emptyList(),
    val disabledChoiceTexts: Set<String> = emptySet(),
    val selectedChoice: ChoiceOption? = null,
    val typedAnswer: String = "",
    val lastCorrect: Boolean? = null,
    val emptyQueue: Boolean = false,
    val error: String? = null,
    val loadingChoices: Boolean = false,
    val typoWarning: Boolean = false,
    val expectedAnswer: String? = null,
    val userTenses: List<String> = emptyList(),
    val activeProfile: com.vocabulario.app.data.api.LanguageProfileResponse? = null,
    val userCefr: String = "A2",
    val showUsages: Boolean = true,
    val showExampleSentences: Boolean = true,
    val showSynonyms: Boolean = true,
    val showAntonyms: Boolean = true,
    val showPeriphrases: Boolean = true,
    val showConjugation: Boolean = true,
    val conjugationExpandedDefault: Boolean = false,
    val relatedWordsExpandedDefault: Boolean = false,
    val showCorrectToast: Boolean = false,
    val showWrongToast: Boolean = false,
    val addTarget: RelatedWord? = null,
    val lists: List<WordListResponse> = emptyList(),
    val pickListOpen: Boolean = false,
    val showCreateListPrompt: Boolean = false,
    val createListName: String = "",
    val learningLang: String = "es",
    val learningLemmas: Set<String> = emptySet(),
    val lastUndo: UndoFrame? = null,
    val isOnline: Boolean = true,
    val correctionOpen: Boolean = false,
    val correctionSubmitting: Boolean = false,
    val correctionResults: CorrectionResultsState = CorrectionResultsState(),
    val correctionQuotaRemaining: Int? = null,
    val selfEditCard: com.vocabulario.app.data.api.CardResponse? = null,
    val selfEditSaving: Boolean = false,
    val selfEditValidating: Boolean = false,
    val selfEditProgressCardId: String? = null,
    val selfEditWarningOpen: Boolean = false,
    val selfEditValidationIssues: List<com.vocabulario.app.data.api.SelfEditValidateIssue> = emptyList(),
    val selfEditPendingContent: kotlinx.serialization.json.JsonObject? = null,
    val historyOpen: Boolean = false,
    val historyEvents: List<com.vocabulario.app.data.api.CardHistoryEventResponse> = emptyList(),
    val historyLoading: Boolean = false,
    val historyRestoring: Boolean = false,
) {
    val canUndo: Boolean get() = lastUndo != null && !grading
}

@HiltViewModel
class PracticeViewModel @Inject constructor(
    private val repository: LearningRepository,
    private val strings: UiStrings,
    private val networkMonitor: com.vocabulario.app.data.NetworkMonitor,
) : ViewModel() {

    private val _state = MutableStateFlow(PracticeUiState(isOnline = networkMonitor.isCurrentlyOnline()))
    val state: StateFlow<PracticeUiState> = _state.asStateFlow()
    private var activityPollJob: Job? = null

    private var inputPref: String = "flashcard"

    init {
        viewModelScope.launch {
            networkMonitor.isOnline.collect { online ->
                _state.value = _state.value.copy(isOnline = online)
            }
        }
    }

    fun loadQueue(append: Boolean = false) {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = !append, error = null)
            runCatching {
                val settings = repository.getSettings()
                val profile = repository.getActiveProfile()
                inputPref = when (settings.practice_input_pref) {
                    "random" -> "choice"
                    else -> settings.practice_input_pref
                }
                Triple(settings, profile, repository.getQueue())
            }.onSuccess { (settings, profile, response) ->
                val items = response.due + response.newCards
                val learningLemmas = runCatching { repository.learningLemmaSet() }.getOrDefault(emptySet())
                if (items.isEmpty() && !append) {
                    _state.value = PracticeUiState(
                        loading = false,
                        emptyQueue = true,
                        isOnline = networkMonitor.isCurrentlyOnline(),
                        learningLemmas = learningLemmas,
                    )
                    return@onSuccess
                }
                val newQueue = if (append) _state.value.queue + items else items
                _state.value = PracticeUiState(
                    loading = false,
                    queue = newQueue,
                    currentIndex = if (append) _state.value.currentIndex else 0,
                    userTenses = normalizeTenseKeys(profile?.selected_tenses.orEmpty()),
                    activeProfile = profile,
                    userCefr = profile?.cefr_level ?: "A2",
                    learningLang = profile?.learning_lang ?: "en",
                    learningLemmas = learningLemmas,
                    isOnline = networkMonitor.isCurrentlyOnline(),
                    showUsages = settings.show_usages,
                    showExampleSentences = settings.show_example_sentences,
                    showSynonyms = settings.show_synonyms_antonyms && settings.show_synonyms,
                    showAntonyms = settings.show_synonyms_antonyms && settings.show_antonyms,
                    showPeriphrases = settings.show_periphrases,
                    showConjugation = settings.show_conjugation,
                    conjugationExpandedDefault = settings.conjugation_expanded_default,
                    relatedWordsExpandedDefault = settings.related_words_expanded_default,
                    lastUndo = null,
                )
                prepareCard()
            }.onFailure {
                _state.value = _state.value.copy(
                    loading = false,
                    error = it.userMessage(strings.get(R.string.err_load_queue)),
                )
            }
        }
    }

    private fun currentItem(): SrsQueueItem? =
        _state.value.queue.getOrNull(_state.value.currentIndex)

    private fun currentDirection(): String =
        currentItem()?.direction ?: "l2_to_l1"

    private fun resolveAnswerMode(): AnswerMode = when (inputPref) {
        "type" -> AnswerMode.TYPE
        "flashcard" -> AnswerMode.FLASHCARD
        else -> AnswerMode.CHOICE
    }

    private fun prepareCard() {
        val mode = resolveAnswerMode()
        _state.value = _state.value.copy(
            answerMode = mode,
            phase = PracticePhase.ANSWERING,
            selectedChoice = null,
            disabledChoiceTexts = emptySet(),
            typedAnswer = "",
            lastCorrect = null,
            expectedAnswer = null,
            typoWarning = false,
        )
        if (mode == AnswerMode.CHOICE) prepareChoices()
    }

    private fun prepareChoices() {
        val item = currentItem() ?: return
        val direction = currentDirection()
        val online = networkMonitor.isCurrentlyOnline()
        viewModelScope.launch {
            _state.value = _state.value.copy(loadingChoices = true)
            runCatching { repository.getDistractors(item.card_id, direction) }
                .onSuccess { response ->
                    val minOptions = if (online) 8 else 4
                    val options = response.options
                    when {
                        options.size >= minOptions -> {
                            _state.value = _state.value.copy(
                                loadingChoices = false,
                                choices = options,
                                error = null,
                            )
                        }
                        !online && options.size >= 2 -> {
                            _state.value = _state.value.copy(
                                loadingChoices = false,
                                choices = options,
                                answerMode = AnswerMode.CHOICE,
                                error = null,
                            )
                        }
                        !online -> {
                            _state.value = _state.value.copy(
                                loadingChoices = false,
                                answerMode = AnswerMode.FLASHCARD,
                                choices = emptyList(),
                                error = null,
                            )
                        }
                        else -> {
                            _state.value = _state.value.copy(
                                loadingChoices = false,
                                error = strings.get(R.string.err_options_count, options.size),
                            )
                        }
                    }
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        loadingChoices = false,
                        error = it.userMessage(strings.get(R.string.err_load_options)),
                    )
                }
        }
    }

    fun onTypedAnswerChange(value: String) {
        _state.value = _state.value.copy(typedAnswer = value)
    }

    fun submitChoice(choice: ChoiceOption) {
        if (_state.value.phase != PracticePhase.ANSWERING) return
        if (choice.text in _state.value.disabledChoiceTexts) return
        if (choice.is_correct) {
            _state.value = _state.value.copy(
                selectedChoice = choice,
                lastCorrect = true,
                showCorrectToast = true,
                phase = PracticePhase.SHOW_CARD,
            )
        } else {
            _state.value = _state.value.copy(
                selectedChoice = choice,
                lastCorrect = false,
                phase = PracticePhase.WRONG_MODAL,
            )
        }
    }

    fun dismissCorrectToast() {
        _state.value = _state.value.copy(showCorrectToast = false)
    }

    fun dismissWrongToast() {
        _state.value = _state.value.copy(showWrongToast = false)
    }

    fun dismissWrongModal() {
        val wrong = _state.value.selectedChoice ?: return
        if (_state.value.phase != PracticePhase.WRONG_MODAL) return
        _state.value = _state.value.copy(
            phase = PracticePhase.ANSWERING,
            disabledChoiceTexts = _state.value.disabledChoiceTexts + wrong.text,
            selectedChoice = null,
        )
    }

    fun submitTyped() {
        val item = currentItem() ?: return
        if (_state.value.phase != PracticePhase.ANSWERING) return
        viewModelScope.launch {
            runCatching {
                repository.checkAnswer(item.card_id, _state.value.typedAnswer, currentDirection())
            }.onSuccess { result ->
                when {
                    result.correct -> {
                        _state.value = _state.value.copy(
                            lastCorrect = true,
                            typoWarning = result.accepted_as_typo,
                            expectedAnswer = result.expected,
                            showCorrectToast = true,
                            phase = PracticePhase.SHOW_CARD,
                        )
                    }
                    else -> {
                        _state.value = _state.value.copy(
                            lastCorrect = false,
                            expectedAnswer = result.expected,
                            typoWarning = false,
                            showWrongToast = true,
                            phase = PracticePhase.SHOW_CARD,
                        )
                    }
                }
            }.onFailure {
                _state.value = _state.value.copy(
                    error = it.userMessage(strings.get(R.string.err_check)),
                )
            }
        }
    }

    fun revealFlashcard() {
        if (_state.value.phase != PracticePhase.ANSWERING) return
        if (_state.value.answerMode != AnswerMode.FLASHCARD) return
        _state.value = _state.value.copy(lastCorrect = true, phase = PracticePhase.SHOW_CARD)
    }

    fun openAddWrongChoice(choice: ChoiceOption) {
        val lemma = choice.lemma_l2 ?: return
        if (choice.in_learning || _state.value.learningLemmas.contains(lemma.trim().lowercase())) {
            _state.value = _state.value.copy(error = strings.get(R.string.err_word_on_list))
            return
        }
        openAddRelated(RelatedWord(lemma, choice.gloss, choice.pos))
    }

    fun addWrongToLearning(choice: ChoiceOption? = _state.value.selectedChoice) {
        val c = choice ?: return
        val lemma = c.lemma_l2 ?: return
        if (c.in_learning) return
        viewModelScope.launch {
            runCatching { repository.createCard(lemma, c.pos, c.gloss, null) }
                .onSuccess {
                    _state.value = _state.value.copy(
                        choices = _state.value.choices.map {
                            if (it.text == c.text) it.copy(in_learning = true) else it
                        },
                    )
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings.get(R.string.err_add)),
                    )
                }
        }
    }

    fun openAddRelated(word: RelatedWord) {
        if (!networkMonitor.isCurrentlyOnline()) {
            _state.value = _state.value.copy(error = strings.get(R.string.import_online_only))
            return
        }
        if (_state.value.learningLemmas.contains(word.lemma.trim().lowercase())) {
            _state.value = _state.value.copy(error = strings.get(R.string.err_word_on_list))
            return
        }
        _state.value = _state.value.copy(
            addTarget = word,
            pickListOpen = false,
            showCreateListPrompt = false,
            createListName = "",
        )
    }

    fun dismissAddSheet() {
        _state.value = _state.value.copy(
            addTarget = null,
            pickListOpen = false,
            showCreateListPrompt = false,
            createListName = "",
        )
    }

    fun openOtherLists() {
        viewModelScope.launch {
            runCatching { repository.listWordLists() }
                .onSuccess { lists ->
                    val custom = lists.filterNot { it.is_system }
                    _state.value = _state.value.copy(
                        lists = lists,
                        pickListOpen = true,
                        showCreateListPrompt = false,
                    )
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings.get(R.string.err_lists)),
                    )
                }
        }
    }

    fun openCreateListPrompt() {
        _state.value = _state.value.copy(showCreateListPrompt = true, pickListOpen = true)
    }

    fun backFromCreateListPrompt() {
        _state.value = _state.value.copy(showCreateListPrompt = false, createListName = "")
    }

    fun backFromListPicker() {
        _state.value = _state.value.copy(pickListOpen = false, showCreateListPrompt = false, createListName = "")
    }

    fun onCreateListNameChange(value: String) {
        _state.value = _state.value.copy(createListName = value)
    }

    fun addRelatedToLearning() {
        val word = _state.value.addTarget ?: return
        if (_state.value.learningLemmas.contains(word.lemma.trim().lowercase())) {
            dismissAddSheet()
            _state.value = _state.value.copy(error = strings.get(R.string.err_word_on_list))
            return
        }
        dismissAddSheet()
        viewModelScope.launch {
            runCatching { repository.createCard(word.lemma, word.pos, word.glossL1, null) }
                .onSuccess {
                    _state.value = _state.value.copy(
                        learningLemmas = _state.value.learningLemmas + word.lemma.trim().lowercase(),
                    )
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings.get(R.string.err_add)),
                    )
                }
        }
    }

    fun addRelatedToList(listId: String) {
        val word = _state.value.addTarget ?: return
        dismissAddSheet()
        viewModelScope.launch {
            runCatching {
                repository.addWordToList(listId, word.lemma, word.pos, word.glossL1, null)
            }.onFailure {
                _state.value = _state.value.copy(
                    error = it.userMessage(strings.get(R.string.err_add)),
                )
            }
        }
    }

    fun createListAndAddRelated() {
        val word = _state.value.addTarget ?: return
        val name = _state.value.createListName.trim()
        if (name.isBlank()) return
        listNameConflictMessage(strings, _state.value.lists, name)?.let {
            _state.value = _state.value.copy(error = it)
            return
        }
        dismissAddSheet()
        viewModelScope.launch {
            runCatching {
                val list = repository.createWordList(name)
                repository.addWordToList(list.id, word.lemma, word.pos, word.glossL1, null)
            }.onFailure {
                _state.value = _state.value.copy(
                    error = it.userMessage(strings.get(R.string.err_create_list)),
                )
            }
        }
    }

    fun grade(grade: String) {
        val item = currentItem() ?: return
        if (_state.value.grading) return
        val correct = _state.value.lastCorrect ?: (_state.value.answerMode == AnswerMode.FLASHCARD)
        val mode = when (_state.value.answerMode) {
            AnswerMode.TYPE -> "type"
            AnswerMode.FLASHCARD -> "flashcard"
            AnswerMode.CHOICE -> "choice"
        }
        viewModelScope.launch {
            val snapshot = repository.cardSrsSnapshot(item.card_id)
                ?: run {
                    _state.value = _state.value.copy(
                        error = strings.get(R.string.err_save_grade),
                    )
                    return@launch
                }
            val undoFrame = UndoFrame(
                clientId = "",
                cardId = item.card_id,
                previousIndex = _state.value.currentIndex,
                previousPhase = _state.value.phase,
                previousAnswerMode = _state.value.answerMode,
                previousTypedAnswer = _state.value.typedAnswer,
                previousLastCorrect = _state.value.lastCorrect,
                snapshot = snapshot,
                wasSessionComplete = false,
            )
            _state.value = _state.value.copy(grading = true, error = null)
            runCatching {
                repository.submitReview(
                    cardId = item.card_id,
                    grade = grade,
                    mode = mode,
                    direction = currentDirection(),
                    correct = correct,
                    answer = _state.value.typedAnswer.takeIf { mode == "type" },
                )
            }.onSuccess { clientId ->
                _state.value = _state.value.copy(
                    lastUndo = undoFrame.copy(clientId = clientId),
                    grading = false,
                )
                advanceToNext()
            }.onFailure {
                _state.value = _state.value.copy(
                    grading = false,
                    error = it.userMessage(strings.get(R.string.err_save_grade)),
                )
            }
        }
    }

    fun undo() {
        val frame = _state.value.lastUndo ?: return
        if (_state.value.grading) return
        viewModelScope.launch {
            _state.value = _state.value.copy(grading = true, error = null)
            runCatching {
                repository.undoReview(frame.clientId, frame.snapshot)
            }.onSuccess {
                _state.value = _state.value.copy(
                    currentIndex = frame.previousIndex,
                    phase = frame.previousPhase,
                    answerMode = frame.previousAnswerMode,
                    typedAnswer = frame.previousTypedAnswer,
                    lastCorrect = frame.previousLastCorrect,
                    emptyQueue = false,
                    lastUndo = null,
                    grading = false,
                    selectedChoice = null,
                    disabledChoiceTexts = emptySet(),
                    showCorrectToast = false,
                    showWrongToast = false,
                )
                prepareCard()
            }.onFailure {
                _state.value = _state.value.copy(
                    grading = false,
                    error = it.userMessage(strings.get(R.string.err_save_grade)),
                )
            }
        }
    }

    fun openCorrection() {
        if (!networkMonitor.isCurrentlyOnline()) {
            _state.value = _state.value.copy(error = strings.get(R.string.correction_requires_online))
            return
        }
        viewModelScope.launch {
            val remaining = runCatching { repository.correctionQuota() }.getOrNull()?.remaining
            _state.value = _state.value.copy(
                correctionOpen = true,
                correctionQuotaRemaining = remaining,
            )
        }
    }

    fun dismissCorrectionReport() {
        _state.value = _state.value.copy(
            correctionOpen = false,
            correctionSubmitting = false,
            correctionQuotaRemaining = null,
        )
    }

    fun openSelfEditFromReport() {
        val item = _state.value.queue.getOrNull(_state.value.currentIndex) ?: return
        _state.value = _state.value.copy(
            correctionOpen = false,
            correctionSubmitting = false,
            selfEditCard = com.vocabulario.app.data.api.CardResponse(
                id = item.card_id,
                lemma_l2 = item.lemma_l2,
                gloss_primary = item.gloss_primary,
                content = item.content,
                created_at = "",
            ),
        )
    }

    fun submitCorrection(sections: List<String>, note: String) {
        if (!networkMonitor.isCurrentlyOnline()) {
            _state.value = _state.value.copy(error = strings.get(R.string.correction_requires_online))
            return
        }
        val cardId = _state.value.queue.getOrNull(_state.value.currentIndex)?.card_id ?: return
        viewModelScope.launch {
            _state.value = _state.value.copy(correctionSubmitting = true, error = null)
            runCatching { repository.submitCardCorrection(cardId, sections, note) }
                .onSuccess {
                    _state.value = _state.value.copy(correctionOpen = false, correctionSubmitting = false)
                    markQueueActivity(cardId, "correction_processing")
                    pollCorrection(cardId)
                    maybeStartActivityPoll()
                }
                .onFailure {
                    val limitMsg = strings.get(R.string.correction_daily_limit)
                    _state.value = _state.value.copy(
                        correctionSubmitting = false,
                        error = if (it.message?.contains("429") == true || it.message?.contains("correction_daily_limit") == true) {
                            limitMsg
                        } else {
                            it.userMessage(strings.get(R.string.err_save))
                        },
                    )
                }
        }
    }

    private fun markQueueActivity(cardId: String, status: String) {
        _state.value = _state.value.copy(
            queue = _state.value.queue.map { item ->
                if (item.card_id == cardId) item.copy(card_activity_status = status) else item
            },
        )
    }

    private fun maybeStartActivityPoll() {
        val hasActivity = _state.value.queue.any { !it.card_activity_status.isNullOrBlank() }
        if (!hasActivity) {
            activityPollJob?.cancel()
            return
        }
        if (activityPollJob?.isActive == true) return
        activityPollJob = viewModelScope.launch {
            while (isActive) {
                delay(2_500)
                loadQueue(append = false)
                if (_state.value.queue.none { !it.card_activity_status.isNullOrBlank() }) break
            }
        }
    }

    private fun selfEditFlowActive(state: PracticeUiState = _state.value): Boolean =
        HomeUiStateSelfEditActive(
            state.selfEditCard,
            state.selfEditWarningOpen,
            state.selfEditProgressCardId,
            state.selfEditSaving,
            state.selfEditValidating,
        )

    private fun deliverCorrectionResult(correction: com.vocabulario.app.data.api.CardCorrectionResponse, lemma: String) {
        val item = CorrectionResultItem(correction, lemma)
        _state.value = _state.value.copy(
            correctionResults = _state.value.correctionResults.enqueue(
                item,
                selfEditFlowActive(),
            ),
        )
    }

    private fun maybeShowNextCorrectionResult() {
        _state.value = _state.value.copy(
            correctionResults = _state.value.correctionResults.tryShowNext(
                selfEditFlowActive(),
            ),
        )
    }

    private fun pollCorrection(cardId: String) {
        viewModelScope.launch {
            repeat(10) {
                kotlinx.coroutines.delay(2_000)
                val latest = runCatching { repository.latestCardCorrection(cardId) }.getOrNull()
                if (latest != null && latest.status != "reported") {
                    val lemma = _state.value.queue.firstOrNull { it.card_id == cardId }?.lemma_l2 ?: "—"
                    deliverCorrectionResult(latest, lemma)
                    repository.syncNow(fullReplace = false)
                    loadQueue(append = false)
                    return@launch
                }
            }
        }
    }

    fun dismissCorrectionResult() {
        _state.value = _state.value.copy(
            correctionResults = _state.value.correctionResults.dismiss(
                selfEditFlowActive(),
            ),
        )
    }

    fun openSelfEditFromResult() {
        val active = _state.value.correctionResults.active ?: return
        val cardId = active.correction.card_id
        val item = _state.value.queue.firstOrNull { it.card_id == cardId }
        _state.value = _state.value.copy(
            correctionResults = _state.value.correctionResults.clearActiveForSelfEdit(),
            selfEditCard = com.vocabulario.app.data.api.CardResponse(
                id = cardId,
                lemma_l2 = item?.lemma_l2 ?: active.cardLemma,
                gloss_primary = item?.gloss_primary,
                content = item?.content ?: buildJsonObject { },
                created_at = "",
            ),
        )
    }

    fun dismissSelfEdit() {
        _state.value = _state.value.copy(
            selfEditCard = null,
            selfEditSaving = false,
            selfEditValidating = false,
            selfEditWarningOpen = false,
            selfEditValidationIssues = emptyList(),
            selfEditPendingContent = null,
        )
        maybeShowNextCorrectionResult()
    }

    fun saveSelfEdit(content: kotlinx.serialization.json.JsonObject) {
        val cardId = _state.value.selfEditCard?.id ?: return
        viewModelScope.launch {
            _state.value = _state.value.copy(selfEditValidating = true)
            runCatching { repository.validateSelfEdit(cardId, content) }
                .onSuccess { validation ->
                    if (validation.ok) {
                        commitSelfEdit(cardId, content)
                    } else {
                        _state.value = _state.value.copy(
                            selfEditValidating = false,
                            selfEditWarningOpen = true,
                            selfEditValidationIssues = validation.issues,
                            selfEditPendingContent = content,
                        )
                    }
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        selfEditValidating = false,
                        error = it.userMessage(strings.get(R.string.err_save)),
                    )
                }
        }
    }

    fun confirmSelfEditWarning() {
        val cardId = _state.value.selfEditCard?.id ?: return
        val content = _state.value.selfEditPendingContent ?: return
        viewModelScope.launch { commitSelfEdit(cardId, content) }
    }

    fun revertSelfEditWarning() {
        dismissSelfEdit()
    }

    private suspend fun commitSelfEdit(cardId: String, content: kotlinx.serialization.json.JsonObject) {
        _state.value = _state.value.copy(
            selfEditSaving = true,
            selfEditValidating = false,
            selfEditWarningOpen = false,
            selfEditValidationIssues = emptyList(),
            selfEditPendingContent = null,
        )
        runCatching { repository.selfEditCard(cardId, content) }
            .onSuccess { updated ->
                _state.value = _state.value.copy(
                    selfEditCard = null,
                    selfEditSaving = false,
                    selfEditValidating = false,
                )
                _state.value = _state.value.copy(
                    queue = _state.value.queue.map { item ->
                        if (item.card_id == updated.id) {
                            item.copy(
                                lemma_l2 = updated.lemma_l2,
                                gloss_primary = updated.gloss_primary,
                                content = updated.content,
                                card_activity_status = updated.card_activity_status,
                                has_content_changes = updated.has_content_changes,
                            )
                        } else item
                    },
                )
                maybeStartActivityPoll()
                loadQueue(append = false)
                maybeShowNextCorrectionResult()
            }
            .onFailure {
                _state.value = _state.value.copy(
                    selfEditSaving = false,
                    selfEditValidating = false,
                    error = it.userMessage(strings.get(R.string.err_save)),
                )
                maybeShowNextCorrectionResult()
            }
    }

    fun openCardHistory() {
        val cardId = _state.value.queue.getOrNull(_state.value.currentIndex)?.card_id ?: return
        if (!_state.value.isOnline) {
            _state.value = _state.value.copy(error = strings.get(R.string.correction_requires_online))
            return
        }
        _state.value = _state.value.copy(historyOpen = true, historyLoading = true, historyEvents = emptyList())
        viewModelScope.launch {
            runCatching { repository.getCardHistory(cardId) }
                .onSuccess { response ->
                    _state.value = _state.value.copy(historyEvents = response.events, historyLoading = false)
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        historyOpen = false,
                        historyLoading = false,
                        error = it.userMessage(strings.get(R.string.err_load_cards)),
                    )
                }
        }
    }

    fun dismissCardHistory() {
        _state.value = _state.value.copy(
            historyOpen = false,
            historyEvents = emptyList(),
            historyLoading = false,
            historyRestoring = false,
        )
    }

    fun restoreFromHistory(eventId: String) {
        val cardId = _state.value.queue.getOrNull(_state.value.currentIndex)?.card_id ?: return
        viewModelScope.launch {
            _state.value = _state.value.copy(historyRestoring = true)
            runCatching { repository.restoreCard(cardId, eventId) }
                .onSuccess {
                    dismissCardHistory()
                    loadQueue(append = false)
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        historyRestoring = false,
                        error = it.userMessage(strings.get(R.string.err_save)),
                    )
                }
        }
    }

    private fun advanceToNext() {
        val next = _state.value.currentIndex + 1
        if (next >= _state.value.queue.size) {
            _state.value = _state.value.copy(
                emptyQueue = true,
                lastUndo = _state.value.lastUndo?.copy(wasSessionComplete = true),
            )
        } else {
            _state.value = _state.value.copy(currentIndex = next)
            prepareCard()
        }
    }
}
