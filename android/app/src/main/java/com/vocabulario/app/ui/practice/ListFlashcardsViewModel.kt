package com.vocabulario.app.ui.practice

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.EnrichmentPoller
import com.vocabulario.app.data.EnrichmentStatus
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.normalizeTenseKeys
import com.vocabulario.app.i18n.UiStrings
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ListFlashcardsUiState(
    val loading: Boolean = true,
    val busy: Boolean = false,
    val empty: Boolean = false,
    val error: String? = null,
    val listTitle: String = "",
    val revealed: Boolean = false,
    val current: CardResponse? = null,
    val progress: Float = 0f,
    val userTenses: List<String> = emptyList(),
    val activeProfile: LanguageProfileResponse? = null,
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
    val finishedSummary: ListFlashcardSummary? = null,
)

@HiltViewModel
class ListFlashcardsViewModel @Inject constructor(
    private val repository: LearningRepository,
    private val strings: UiStrings,
    private val enrichmentPoller: EnrichmentPoller,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val listId: String = savedStateHandle.get<String>("listId").orEmpty()
    private var queue = ListFlashcardQueue(emptyList())
    private var systemListId: String? = null
    private var currentCardJob: Job? = null

    private val _state = MutableStateFlow(ListFlashcardsUiState())
    val state: StateFlow<ListFlashcardsUiState> = _state.asStateFlow()
    val enrichmentPollingIds: StateFlow<Set<String>> = enrichmentPoller.pollingIds

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            runCatching {
                val lists = repository.listWordLists()
                systemListId = lists.firstOrNull { it.is_system }?.id
                val list = lists.firstOrNull { it.id == listId }
                val settings = repository.getSettings()
                val profile = repository.getActiveProfile()
                val cards = if (list == null || list.is_system || list.is_pending_inbox) {
                    emptyList()
                } else {
                    eligibleListFlashcards(repository.listWords(listId))
                }
                Triple(list, settings to profile, cards)
            }.onSuccess { (list, settingsProfile, cards) ->
                val (settings, profile) = settingsProfile
                queue = ListFlashcardQueue(cards)
                _state.value = ListFlashcardsUiState(
                    loading = false,
                    empty = cards.isEmpty(),
                    listTitle = list?.name.orEmpty(),
                    current = queue.current,
                    revealed = false,
                    progress = queue.progress,
                    userTenses = normalizeTenseKeys(
                        profile?.selected_tenses.orEmpty(),
                        profile?.learning_lang,
                    ),
                    activeProfile = profile,
                    userCefr = profile?.cefr_level ?: "A2",
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
                )
                enrichmentPoller.watchCards(
                    cards.filter {
                        EnrichmentStatus.needsPoll(it.enrichment_status) ||
                            !it.card_activity_status.isNullOrBlank()
                    },
                )
                observeCurrentCard()
            }.onFailure {
                _state.value = _state.value.copy(
                    loading = false,
                    error = it.userMessage(strings, R.string.err_load_cards),
                )
            }
        }
    }

    fun reveal() {
        if (_state.value.busy || _state.value.revealed) return
        queue.reveal()
        _state.value = _state.value.copy(revealed = true, progress = queue.progress)
    }

    fun next() {
        if (_state.value.busy || !_state.value.revealed) return
        if (queue.next()) {
            finish(queue.snapshot())
        } else {
            publishCurrent()
        }
    }

    fun addToLearning() {
        if (_state.value.busy || !_state.value.revealed) return
        val card = queue.current ?: return
        val target = systemListId
        if (target.isNullOrBlank()) {
            _state.value = _state.value.copy(error = strings.get(R.string.err_move))
            return
        }
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true, error = null)
            runCatching { repository.moveCards(listOf(card.id), target) }
                .onSuccess {
                    if (queue.commitAdd()) {
                        finish(queue.snapshot())
                    } else {
                        publishCurrent(busy = false)
                    }
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        busy = false,
                        error = it.userMessage(strings, R.string.err_move),
                    )
                }
        }
    }

    fun exit() {
        if (_state.value.finishedSummary != null) return
        finish(queue.snapshotIncludingCurrent())
    }

    private fun publishCurrent(busy: Boolean = false) {
        _state.value = _state.value.copy(
            busy = busy,
            error = null,
            current = queue.current,
            revealed = false,
            progress = queue.progress,
            empty = queue.isFinished,
        )
        observeCurrentCard()
    }

    private fun observeCurrentCard() {
        val card = queue.current ?: run {
            currentCardJob?.cancel()
            currentCardJob = null
            return
        }
        enrichmentPoller.watchCard(card)
        currentCardJob?.cancel()
        currentCardJob = viewModelScope.launch {
            repository.observeCard(card.id).collect { updated ->
                if (updated == null) return@collect
                if (_state.value.current?.id != card.id) return@collect
                _state.value = _state.value.copy(current = updated)
            }
        }
    }

    private fun finish(summary: ListFlashcardSummary) {
        _state.value = _state.value.copy(
            busy = false,
            finishedSummary = summary,
        )
    }
}
