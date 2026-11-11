package com.vocabulario.app.ui.practice

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.BlockingBusy
import com.vocabulario.app.data.EnrichmentPoller
import com.vocabulario.app.data.EnrichmentStatus
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.ChoiceOption
import com.vocabulario.app.data.api.SrsQueueItem
import com.vocabulario.app.data.api.SyncSrsState
import com.vocabulario.app.data.api.WordListResponse
import com.vocabulario.app.data.api.isWordAlreadyOnList
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.RelatedMembershipIndex
import com.vocabulario.app.data.containsLemma
import com.vocabulario.app.data.formatLemmaWithArticle
import com.vocabulario.app.data.lemmaKeys
import com.vocabulario.app.data.local.LocalAnswerCheck
import com.vocabulario.app.data.normalizeTenseKeys
import com.vocabulario.app.i18n.UiStrings
import com.vocabulario.app.ui.card.RelatedWord
import com.vocabulario.app.ui.card.CorrectionResultItem
import com.vocabulario.app.ui.card.CorrectionResultsState
import com.vocabulario.app.ui.home.listNameConflictMessage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
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
    val synonymWarning: Boolean = false,
    val expectedAnswer: String? = null,
    val userTenses: List<String> = emptyList(),
    val activeProfile: com.vocabulario.app.data.api.LanguageProfileResponse? = null,
    val userCefr: String = "A2",
    val showUsages: Boolean = true,
    val showExampleSentences: Boolean = true,
    val showSynonyms: Boolean = true,
    val showAntonyms: Boolean = true,
    val showWordFamily: Boolean = true,
    val showAssociations: Boolean = true,
    val showPeriphrases: Boolean = true,
    val showConjugation: Boolean = true,
    val conjugationExpandedDefault: Boolean = false,
    val relatedWordsExpandedDefault: Boolean = false,
    val showCorrectToast: Boolean = false,
    val showAlmostToast: Boolean = false,
    val showWrongToast: Boolean = false,
    val addTarget: RelatedWord? = null,
    val lists: List<WordListResponse> = emptyList(),
    val pickListOpen: Boolean = false,
    val showCreateListPrompt: Boolean = false,
    val createListName: String = "",
    val learningLang: String = "es",
    val learningLemmas: Set<String> = emptySet(),
    val relatedMembership: RelatedMembershipIndex = RelatedMembershipIndex.Empty,
    val lastUndo: UndoFrame? = null,
    val isOnline: Boolean = true,
    val correctionOpen: Boolean = false,
    val correctionSubmitting: Boolean = false,
    val correctionResults: CorrectionResultsState = CorrectionResultsState(),
    val correctionQuotaRemaining: Int? = null,
    val correctionEscalating: Boolean = false,
    val historyOpen: Boolean = false,
    val historyEvents: List<com.vocabulario.app.data.api.CardHistoryEventResponse> = emptyList(),
    val historyLoading: Boolean = false,
) {
    val canUndo: Boolean get() = lastUndo != null && !grading
}

@HiltViewModel
class PracticeViewModel @Inject constructor(
    private val repository: LearningRepository,
    private val strings: UiStrings,
    private val networkMonitor: com.vocabulario.app.data.NetworkMonitor,
    private val enrichmentPoller: EnrichmentPoller,
    private val blockingBusy: BlockingBusy,
) : ViewModel() {

    private val _state = MutableStateFlow(PracticeUiState(isOnline = networkMonitor.isCurrentlyOnline()))
    val state: StateFlow<PracticeUiState> = _state.asStateFlow()
    val enrichmentPollingIds: StateFlow<Set<String>> = enrichmentPoller.pollingIds
    private var activityPollJob: Job? = null
    private var currentCardJob: Job? = null

    private var inputPref: String = "flashcard"
    private val usedDistractorKeys = mutableSetOf<String>()

    init {
        viewModelScope.launch {
            networkMonitor.isOnline.collect { online ->
                _state.value = _state.value.copy(isOnline = online)
            }
        }
    }

    fun loadQueue(append: Boolean = false) {
        viewModelScope.launch {
            val keepVisible = append || _state.value.queue.isNotEmpty()
            _state.value = _state.value.copy(loading = !keepVisible, error = null)
            if (!append) usedDistractorKeys.clear()
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
                val learningLemmas = runCatching { repository.learningLemmaSet() }.getOrDefault(emptySet()) +
                    _state.value.learningLemmas
                val relatedMembership = runCatching { repository.relatedMembershipIndex() }
                    .getOrDefault(RelatedMembershipIndex.Empty)
                if (items.isEmpty() && !append) {
                    _state.value = PracticeUiState(
                        loading = false,
                        emptyQueue = true,
                        isOnline = networkMonitor.isCurrentlyOnline(),
                        learningLemmas = learningLemmas,
                        relatedMembership = relatedMembership,
                    )
                    return@onSuccess
                }
                val newQueue = if (append) _state.value.queue + items else items
                _state.value = PracticeUiState(
                    loading = false,
                    queue = newQueue,
                    currentIndex = if (append) _state.value.currentIndex else 0,
                    userTenses = normalizeTenseKeys(profile?.selected_tenses.orEmpty(), profile?.learning_lang),
                    activeProfile = profile,
                    userCefr = profile?.cefr_level ?: "A2",
                    learningLang = profile?.learning_lang ?: "en",
                    learningLemmas = learningLemmas,
                    relatedMembership = relatedMembership,
                    isOnline = networkMonitor.isCurrentlyOnline(),
                    showUsages = settings.show_usages,
                    showExampleSentences = settings.show_example_sentences,
                    showSynonyms = settings.show_synonyms_antonyms && settings.show_synonyms,
                    showAntonyms = settings.show_synonyms_antonyms && settings.show_antonyms,
                    showWordFamily = settings.show_word_family,
                    showAssociations = settings.show_associations,
                    showPeriphrases = settings.show_periphrases,
                    showConjugation = settings.show_conjugation,
                    conjugationExpandedDefault = settings.conjugation_expanded_default,
                    relatedWordsExpandedDefault = settings.related_words_expanded_default,
                    lastUndo = null,
                )
                enrichmentPoller.watch(
                    newQueue.map {
                        EnrichmentPoller.Watch(
                            id = it.card_id,
                            status = EnrichmentStatus.LEARNABLE,
                            activity = it.card_activity_status,
                        )
                    },
                )
                prepareCard()
            }.onFailure {
                _state.value = _state.value.copy(
                    loading = false,
                    error = it.userMessage(strings, R.string.err_load_queue),
                )
            }
        }
    }

    private fun currentItem(): SrsQueueItem? =
        _state.value.queue.getOrNull(_state.value.currentIndex)

    private fun observeCurrentQueueCard() {
        val item = currentItem() ?: run {
            currentCardJob?.cancel()
            currentCardJob = null
            return
        }
        enrichmentPoller.watch(
            listOf(
                EnrichmentPoller.Watch(
                    id = item.card_id,
                    status = EnrichmentStatus.LEARNABLE,
                    activity = item.card_activity_status,
                ),
            ),
        )
        currentCardJob?.cancel()
        currentCardJob = viewModelScope.launch {
            repository.observeCard(item.card_id).collect { updated ->
                if (updated == null) return@collect
                val idx = _state.value.currentIndex
                val current = _state.value.queue.getOrNull(idx) ?: return@collect
                if (current.card_id != updated.id) return@collect
                val merged = current.copy(
                    content = updated.content,
                    card_activity_status = updated.card_activity_status ?: current.card_activity_status,
                    has_content_changes = updated.has_content_changes,
                )
                _state.value = _state.value.copy(
                    queue = _state.value.queue.toMutableList().also { it[idx] = merged },
                )
            }
        }
    }

    private fun currentDirection(): String =
        currentItem()?.direction ?: "l2_to_l1"

    private fun resolveAnswerMode(): AnswerMode {
        val item = currentItem()
        return when (inputPref) {
            "type" -> AnswerMode.TYPE
            "flashcard" -> AnswerMode.FLASHCARD
            else -> AnswerMode.CHOICE
        }
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
            synonymWarning = false,
        )
        observeCurrentQueueCard()
        if (mode == AnswerMode.CHOICE) prepareChoices()
    }

    fun showHints() {
        if (_state.value.phase != PracticePhase.ANSWERING) return
        if (_state.value.answerMode != AnswerMode.TYPE) return
        if (_state.value.loadingChoices) return
        _state.value = _state.value.copy(
            answerMode = AnswerMode.CHOICE,
            loadingChoices = true,
            typedAnswer = "",
            selectedChoice = null,
            disabledChoiceTexts = emptySet(),
        )
        prepareChoices(fromTypingHints = true)
    }

    private fun prepareChoices(fromTypingHints: Boolean = false) {
        val item = currentItem() ?: return
        val direction = currentDirection()
        viewModelScope.launch {
            _state.value = _state.value.copy(loadingChoices = true)
            runCatching { repository.getDistractors(item.card_id, direction, usedDistractorKeys) }
                .onSuccess { pick ->
                    if (pick.unusedPoolWasEmpty) usedDistractorKeys.clear()
                    usedDistractorKeys += pick.usedListKeys
                    val options = pick.response.options.withLearningFlags(_state.value.learningLemmas)
                    when {
                        options.size >= 2 -> {
                            _state.value = _state.value.copy(
                                loadingChoices = false,
                                choices = options,
                                error = null,
                            )
                        }
                        else -> {
                            _state.value = if (fromTypingHints) {
                                _state.value.copy(
                                    loadingChoices = false,
                                    lastCorrect = false,
                                    phase = PracticePhase.SHOW_CARD,
                                    choices = emptyList(),
                                    error = null,
                                )
                            } else {
                                _state.value.copy(
                                    loadingChoices = false,
                                    answerMode = AnswerMode.FLASHCARD,
                                    choices = emptyList(),
                                    error = null,
                                )
                            }
                        }
                    }
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        loadingChoices = false,
                        answerMode = if (fromTypingHints) AnswerMode.TYPE else _state.value.answerMode,
                        error = it.userMessage(strings, R.string.err_load_options),
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

    fun dismissAlmostToast() {
        _state.value = _state.value.copy(showAlmostToast = false)
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
        if (blockingBusy.busy.value) return
        blockingBusy.launchIn(viewModelScope) {
            runCatching {
                repository.checkAnswer(item.card_id, _state.value.typedAnswer, currentDirection())
            }.onSuccess { result ->
                when {
                    result.correct && result.accepted_as_typo -> {
                        val query = result.expected ?: _state.value.typedAnswer
                        val syn = if (result.accepted_as_synonym) {
                            LocalAnswerCheck.resolveSynonym(
                                item.content,
                                currentDirection(),
                                query,
                            )
                        } else {
                            null
                        }
                        _state.value = _state.value.copy(
                            lastCorrect = true,
                            typoWarning = true,
                            synonymWarning = result.accepted_as_synonym,
                            expectedAnswer = syn?.displayLemma ?: result.expected,
                            showAlmostToast = true,
                            showCorrectToast = false,
                            showWrongToast = false,
                            phase = PracticePhase.SHOW_CARD,
                        )
                    }
                    result.correct && result.accepted_as_synonym -> {
                        val syn = LocalAnswerCheck.resolveSynonym(
                            item.content,
                            currentDirection(),
                            _state.value.typedAnswer,
                        )
                        val gloss = syn?.glossL1?.trim()?.takeIf { it.isNotEmpty() }
                            ?: item.gloss_primary?.trim().orEmpty().ifBlank { result.expected }
                        _state.value = _state.value.copy(
                            lastCorrect = true,
                            typoWarning = false,
                            synonymWarning = true,
                            expectedAnswer = gloss,
                            showCorrectToast = true,
                            showAlmostToast = false,
                            showWrongToast = false,
                            phase = PracticePhase.SHOW_CARD,
                        )
                    }
                    result.correct -> {
                        _state.value = _state.value.copy(
                            lastCorrect = true,
                            typoWarning = false,
                            synonymWarning = false,
                            expectedAnswer = result.expected,
                            showCorrectToast = true,
                            showAlmostToast = false,
                            showWrongToast = false,
                            phase = PracticePhase.SHOW_CARD,
                        )
                    }
                    else -> {
                        _state.value = _state.value.copy(
                            lastCorrect = false,
                            expectedAnswer = result.expected,
                            typoWarning = false,
                            synonymWarning = false,
                            showWrongToast = true,
                            showCorrectToast = false,
                            showAlmostToast = false,
                            phase = PracticePhase.SHOW_CARD,
                        )
                    }
                }
            }.onFailure {
                _state.value = _state.value.copy(
                    error = it.userMessage(strings, R.string.err_check),
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
        val lemma = choice.lemma_l2?.trim()?.takeIf { it.isNotEmpty() } ?: return
        if (choice.in_learning || _state.value.learningLemmas.containsLemma(lemma)) {
            markLemmaAdded(lemma)
            return
        }
        openAddRelated(RelatedWord(lemma, choice.gloss, choice.pos))
    }

    fun addWrongToLearning(choice: ChoiceOption? = _state.value.selectedChoice) {
        val c = choice ?: return
        val lemma = c.lemma_l2?.trim()?.takeIf { it.isNotEmpty() } ?: return
        if (c.in_learning || _state.value.learningLemmas.containsLemma(lemma)) {
            markLemmaAdded(lemma)
            return
        }
        markLemmaAdded(lemma)
        viewModelScope.launch {
            runCatching { repository.createCard(lemma, c.pos, c.gloss, null) }
                .onSuccess { created ->
                    markLemmaAdded(created.lemma_l2.ifBlank { lemma })
                }
                .onFailure { e ->
                    if (e.isWordAlreadyOnList()) {
                        markLemmaAdded(lemma)
                    } else {
                        unmarkLemma(lemma)
                        _state.value = _state.value.copy(
                            error = e.userMessage(strings, R.string.err_add),
                        )
                    }
                }
        }
    }

    fun openAddRelated(word: RelatedWord) {
        if (!networkMonitor.isCurrentlyOnline()) {
            _state.value = _state.value.copy(error = strings.get(R.string.import_online_only))
            return
        }
        if (_state.value.relatedMembership.find(word.lemma, word.pos) != null ||
            _state.value.learningLemmas.containsLemma(word.lemma)
        ) {
            markLemmaAdded(word.lemma)
            return
        }
        _state.value = _state.value.copy(
            addTarget = word.copy(
                sourceCardId = if (word.joinWordFamily) {
                    _state.value.queue.getOrNull(_state.value.currentIndex)?.card_id
                } else {
                    null
                },
            ),
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
        blockingBusy.launchIn(viewModelScope) {
            runCatching { repository.listWordLists() }
                .onSuccess { lists ->
                    _state.value = _state.value.copy(
                        lists = lists,
                        pickListOpen = true,
                        showCreateListPrompt = false,
                    )
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_lists),
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
        dismissAddSheet()
        markLemmaAdded(word.lemma)
        viewModelScope.launch {
            runCatching {
                repository.createCard(
                    formatLemmaWithArticle(word.lemma, word.article),
                    word.pos,
                    word.glossL1,
                    null,
                    sourceCardId = word.sourceCardId,
                )
            }
                .onSuccess { created ->
                    markLemmaAdded(created.lemma_l2.ifBlank { word.lemma })
                }
                .onFailure { e ->
                    if (e.isWordAlreadyOnList()) {
                        markLemmaAdded(word.lemma)
                    } else {
                        unmarkLemma(word.lemma)
                        _state.value = _state.value.copy(
                            error = e.userMessage(strings, R.string.err_add),
                        )
                    }
                }
        }
    }

    private fun markLemmaAdded(lemma: String) {
        applyLemmaLearning(lemma, added = true)
    }

    private fun unmarkLemma(lemma: String) {
        applyLemmaLearning(lemma, added = false)
    }

    private fun applyLemmaLearning(lemma: String, added: Boolean) {
        val keys = lemmaKeys(lemma)
        if (keys.isEmpty()) return
        _state.value = _state.value.copy(
            learningLemmas = if (added) {
                _state.value.learningLemmas + keys
            } else {
                _state.value.learningLemmas - keys
            },
            choices = _state.value.choices.map { choice ->
                if (lemmaKeys(choice.lemma_l2).any { it in keys }) {
                    choice.copy(in_learning = added)
                } else {
                    choice
                }
            },
        )
    }

    private fun List<ChoiceOption>.withLearningFlags(lemmas: Set<String>): List<ChoiceOption> =
        map { choice ->
            if (choice.in_learning || lemmas.containsLemma(choice.lemma_l2)) {
                choice.copy(in_learning = true)
            } else {
                choice
            }
        }

    fun addRelatedToList(listId: String) {
        val word = _state.value.addTarget ?: return
        dismissAddSheet()
        blockingBusy.launchIn(viewModelScope) {
            runCatching {
                repository.addWordToList(
                    listId,
                    formatLemmaWithArticle(word.lemma, word.article),
                    word.pos,
                    word.glossL1,
                    null,
                    sourceCardId = word.sourceCardId,
                )
            }.onFailure {
                _state.value = _state.value.copy(
                    error = it.userMessage(strings, R.string.err_add),
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
        blockingBusy.launchIn(viewModelScope) {
            runCatching {
                val list = repository.createWordList(name)
                repository.addWordToList(
                    list.id,
                    formatLemmaWithArticle(word.lemma, word.article),
                    word.pos,
                    word.glossL1,
                    null,
                    sourceCardId = word.sourceCardId,
                )
            }.onFailure {
                _state.value = _state.value.copy(
                    error = it.userMessage(strings, R.string.err_create_list),
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
            _state.value = _state.value.copy(grading = true, error = null)
            val snapshot = repository.cardSrsSnapshot(item.card_id)
            val undoFrame = snapshot?.let {
                UndoFrame(
                    clientId = "",
                    cardId = item.card_id,
                    previousIndex = _state.value.currentIndex,
                    previousPhase = _state.value.phase,
                    previousAnswerMode = _state.value.answerMode,
                    previousTypedAnswer = _state.value.typedAnswer,
                    previousLastCorrect = _state.value.lastCorrect,
                    snapshot = it,
                    wasSessionComplete = false,
                )
            }
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
                    lastUndo = undoFrame?.copy(clientId = clientId),
                    grading = false,
                )
                advanceToNext()
            }.onFailure {
                _state.value = _state.value.copy(
                    grading = false,
                    error = it.userMessage(strings, R.string.err_save_grade),
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
                    showAlmostToast = false,
                    showWrongToast = false,
                )
                prepareCard()
            }.onFailure {
                _state.value = _state.value.copy(
                    grading = false,
                    error = it.userMessage(strings, R.string.err_save_grade),
                )
            }
        }
    }

    fun openCorrection() {
        if (!com.vocabulario.app.ui.card.CARD_CORRECTION_ENABLED) return
        if (!networkMonitor.isCurrentlyOnline()) {
            _state.value = _state.value.copy(error = strings.get(R.string.correction_requires_online))
            return
        }
        _state.value = _state.value.copy(correctionOpen = true)
        viewModelScope.launch {
            val remaining = runCatching { repository.correctionQuota() }.getOrNull()?.remaining
            if (!_state.value.correctionOpen) return@launch
            _state.value = _state.value.copy(correctionQuotaRemaining = remaining)
        }
    }

    fun dismissCorrectionReport() {
        _state.value = _state.value.copy(
            correctionOpen = false,
            correctionSubmitting = false,
            correctionQuotaRemaining = null,
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
                    _state.value = _state.value.copy(
                        correctionSubmitting = false,
                        error = it.userMessage(strings, R.string.err_save),
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

    private fun deliverCorrectionResult(correction: com.vocabulario.app.data.api.CardCorrectionResponse, lemma: String) {
        val item = CorrectionResultItem(correction, lemma)
        _state.value = _state.value.copy(
            correctionResults = _state.value.correctionResults.enqueue(item),
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
            correctionResults = _state.value.correctionResults.dismiss(),
            correctionEscalating = false,
        )
    }

    fun escalateRejectedCorrection() {
        val active = _state.value.correctionResults.active ?: return
        val correction = active.correction
        if (correction.status == "accepted") return
        viewModelScope.launch {
            _state.value = _state.value.copy(correctionEscalating = true, error = null)
            runCatching {
                repository.escalateCardCorrection(correction.card_id, correction.id)
            }.onSuccess {
                _state.value = _state.value.copy(correctionEscalating = false)
                dismissCorrectionResult()
            }.onFailure {
                _state.value = _state.value.copy(
                    correctionEscalating = false,
                    error = it.userMessage(strings, R.string.err_save),
                )
            }
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
                        error = it.userMessage(strings, R.string.err_load_cards),
                    )
                }
        }
    }

    fun dismissCardHistory() {
        _state.value = _state.value.copy(
            historyOpen = false,
            historyEvents = emptyList(),
            historyLoading = false,
        )
    }

    private fun advanceToNext() {
        val next = _state.value.currentIndex + 1
        if (next >= _state.value.queue.size) {
            _state.value = _state.value.copy(
                emptyQueue = true,
                lastUndo = _state.value.lastUndo?.copy(wasSessionComplete = true),
            )
        } else {
            val mode = resolveAnswerMode()
            _state.value = _state.value.copy(
                currentIndex = next,
                answerMode = mode,
                phase = PracticePhase.ANSWERING,
                selectedChoice = null,
                disabledChoiceTexts = emptySet(),
                typedAnswer = "",
                lastCorrect = null,
                expectedAnswer = null,
                typoWarning = false,
                synonymWarning = false,
            )
            if (mode == AnswerMode.CHOICE) prepareChoices()
        }
    }
}
