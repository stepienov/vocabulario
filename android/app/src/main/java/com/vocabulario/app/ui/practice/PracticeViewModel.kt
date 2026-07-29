package com.vocabulario.app.ui.practice

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.ChoiceOption
import com.vocabulario.app.data.api.SrsQueueItem
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.ui.card.RelatedWord
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
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

data class PracticeUiState(
    val loading: Boolean = false,
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
    val userCefr: String = "A2",
    val showUsages: Boolean = true,
    val showExampleSentences: Boolean = true,
    val showSynonymsAntonyms: Boolean = true,
    val showPeriphrases: Boolean = true,
    val conjugationExpandedDefault: Boolean = false,
    val relatedWordsExpandedDefault: Boolean = false,
)

@HiltViewModel
class PracticeViewModel @Inject constructor(
    private val repository: LearningRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(PracticeUiState())
    val state: StateFlow<PracticeUiState> = _state.asStateFlow()

    private var inputPref: String = "choice"

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
                if (items.isEmpty() && !append) {
                    _state.value = PracticeUiState(loading = false, emptyQueue = true)
                    return@onSuccess
                }
                val newQueue = if (append) _state.value.queue + items else items
                _state.value = PracticeUiState(
                    loading = false,
                    queue = newQueue,
                    currentIndex = if (append) _state.value.currentIndex else 0,
                    userTenses = profile?.selected_tenses.orEmpty(),
                    userCefr = profile?.cefr_level ?: "A2",
                    showUsages = settings.show_usages,
                    showExampleSentences = settings.show_example_sentences,
                    showSynonymsAntonyms = settings.show_synonyms_antonyms,
                    showPeriphrases = settings.show_periphrases,
                    conjugationExpandedDefault = settings.conjugation_expanded_default,
                    relatedWordsExpandedDefault = settings.related_words_expanded_default,
                )
                prepareCard()
            }.onFailure {
                _state.value = _state.value.copy(
                    loading = false,
                    error = it.userMessage("Błąd ładowania kolejki"),
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
        viewModelScope.launch {
            _state.value = _state.value.copy(loadingChoices = true)
            runCatching { repository.getDistractors(item.card_id, direction) }
                .onSuccess { response ->
                    _state.value = _state.value.copy(
                        loadingChoices = false,
                        choices = response.options,
                        error = if (response.options.size < 8) {
                            "Oczekiwano 8 opcji, otrzymano ${response.options.size}. Dodaj słowo ponownie."
                        } else null,
                    )
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        loadingChoices = false,
                        error = it.userMessage("Błąd ładowania opcji"),
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
                            phase = PracticePhase.SHOW_CARD,
                        )
                    }
                    else -> {
                        _state.value = _state.value.copy(
                            lastCorrect = false,
                            expectedAnswer = result.expected,
                            typoWarning = false,
                            phase = PracticePhase.SHOW_CARD,
                        )
                    }
                }
            }.onFailure {
                _state.value = _state.value.copy(error = it.userMessage("Błąd sprawdzania"))
            }
        }
    }

    fun revealFlashcard() {
        if (_state.value.phase != PracticePhase.ANSWERING) return
        if (_state.value.answerMode != AnswerMode.FLASHCARD) return
        _state.value = _state.value.copy(lastCorrect = true, phase = PracticePhase.SHOW_CARD)
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
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd dodawania")) }
        }
    }

    fun addWrongToFavorites(choice: ChoiceOption? = _state.value.selectedChoice) {
        val c = choice ?: return
        val lemma = c.lemma_l2 ?: return
        if (c.is_favorite) return
        viewModelScope.launch {
            runCatching { repository.addFavorite(lemma, c.pos, c.gloss) }
                .onSuccess {
                    _state.value = _state.value.copy(
                        choices = _state.value.choices.map {
                            if (it.text == c.text) it.copy(is_favorite = true) else it
                        },
                    )
                }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd ulubionych")) }
        }
    }

    fun addRelatedToLearning(word: RelatedWord) {
        viewModelScope.launch {
            runCatching { repository.createCard(word.lemma, word.pos, word.glossL1, null) }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd dodawania")) }
        }
    }

    fun addRelatedToFavorites(word: RelatedWord) {
        viewModelScope.launch {
            runCatching { repository.addFavorite(word.lemma, word.pos, word.glossL1) }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd ulubionych")) }
        }
    }

    fun grade(grade: String) {
        val item = currentItem() ?: return
        val correct = _state.value.lastCorrect ?: (_state.value.answerMode == AnswerMode.FLASHCARD)
        val mode = when (_state.value.answerMode) {
            AnswerMode.TYPE -> "type"
            AnswerMode.FLASHCARD -> "flashcard"
            AnswerMode.CHOICE -> "choice"
        }
        viewModelScope.launch {
            runCatching {
                repository.submitReview(
                    cardId = item.card_id,
                    grade = grade,
                    mode = mode,
                    direction = currentDirection(),
                    correct = correct,
                    answer = _state.value.typedAnswer.takeIf { mode == "type" },
                )
            }.onSuccess { advanceToNext() }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd zapisu oceny")) }
        }
    }

    private fun advanceToNext() {
        val next = _state.value.currentIndex + 1
        if (next >= _state.value.queue.size) {
            loadQueue(append = false)
        } else {
            _state.value = _state.value.copy(currentIndex = next)
            prepareCard()
        }
    }
}
