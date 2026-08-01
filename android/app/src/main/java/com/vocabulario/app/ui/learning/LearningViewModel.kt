package com.vocabulario.app.ui.learning

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.WordListResponse
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.normalizeTenseKeys
import com.vocabulario.app.ui.card.RelatedWord
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

data class LearningUiState(
    val cards: List<CardResponse> = emptyList(),
    val selectedCard: CardResponse? = null,
    val userTenses: List<String> = emptyList(),
    val userCefr: String = "A2",
    val loading: Boolean = false,
    val error: String? = null,
    val message: String? = null,
    val addTarget: RelatedWord? = null,
    val lists: List<WordListResponse> = emptyList(),
    val pickListOpen: Boolean = false,
    val showCreateListPrompt: Boolean = false,
    val createListName: String = "",
)

@HiltViewModel
class LearningViewModel @Inject constructor(
    private val repository: LearningRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(LearningUiState())
    val state: StateFlow<LearningUiState> = _state.asStateFlow()
    private var pollJob: Job? = null

    fun load() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            val profile = runCatching { repository.getActiveProfile() }.getOrNull()
            runCatching { repository.listCards() }
                .onSuccess { cards ->
                    _state.value = LearningUiState(
                        loading = false,
                        cards = cards,
                        selectedCard = syncSelected(cards, _state.value.selectedCard),
                        userTenses = normalizeTenseKeys(profile?.selected_tenses.orEmpty()),
                        userCefr = profile?.cefr_level ?: "A2",
                    )
                    startPollingIfNeeded(cards)
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        loading = false,
                        error = it.userMessage("Błąd ładowania kart"),
                    )
                }
        }
    }

    fun selectCard(card: CardResponse) {
        _state.value = _state.value.copy(selectedCard = card)
    }

    fun clearSelection() {
        _state.value = _state.value.copy(selectedCard = null)
    }

    fun openAddRelated(word: RelatedWord) {
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
                        showCreateListPrompt = custom.isEmpty(),
                    )
                }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd list")) }
        }
    }

    fun openCreateListPrompt() {
        _state.value = _state.value.copy(showCreateListPrompt = true, pickListOpen = true)
    }

    fun onCreateListNameChange(value: String) {
        _state.value = _state.value.copy(createListName = value)
    }

    fun addRelatedToLearning() {
        val word = _state.value.addTarget ?: return
        dismissAddSheet()
        viewModelScope.launch {
            runCatching { repository.createCard(word.lemma, word.pos, word.glossL1, null) }
                .onSuccess {
                    _state.value = _state.value.copy(message = "Dodano do nauki: ${word.lemma}")
                    load()
                }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd dodawania")) }
        }
    }

    fun addRelatedToList(listId: String) {
        val word = _state.value.addTarget ?: return
        dismissAddSheet()
        viewModelScope.launch {
            runCatching {
                repository.addWordToList(listId, word.lemma, word.pos, word.glossL1, null)
            }.onSuccess {
                _state.value = _state.value.copy(message = "Dodano: ${word.lemma}")
                load()
            }.onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd dodawania")) }
        }
    }

    fun createListAndAddRelated() {
        val word = _state.value.addTarget ?: return
        val name = _state.value.createListName.trim()
        if (name.isBlank()) return
        listNameConflictMessage(_state.value.lists, name)?.let {
            _state.value = _state.value.copy(error = it)
            return
        }
        dismissAddSheet()
        viewModelScope.launch {
            runCatching {
                val list = repository.createWordList(name)
                repository.addWordToList(list.id, word.lemma, word.pos, word.glossL1, null)
            }.onSuccess {
                _state.value = _state.value.copy(message = "Dodano: ${word.lemma}")
                load()
            }.onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd tworzenia listy")) }
        }
    }

    private fun startPollingIfNeeded(cards: List<CardResponse>) {
        pollJob?.cancel()
        if (cards.none { it.enrichment_status == "pending" }) return
        pollJob = viewModelScope.launch {
            while (isActive) {
                delay(3_000)
                val refreshed = runCatching { repository.listCards() }.getOrNull() ?: continue
                val current = _state.value
                _state.value = current.copy(
                    cards = refreshed,
                    selectedCard = syncSelected(refreshed, current.selectedCard),
                )
                if (refreshed.none { it.enrichment_status == "pending" }) break
            }
        }
    }

    private fun syncSelected(
        cards: List<CardResponse>,
        selected: CardResponse?,
    ): CardResponse? {
        if (selected == null) return null
        return cards.firstOrNull { it.id == selected.id } ?: selected
    }
}
