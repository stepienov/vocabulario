package com.vocabulario.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.DashboardStatsResponse
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.api.WordListResponse
import com.vocabulario.app.data.api.userMessage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import javax.inject.Inject

enum class HomeTab { DASHBOARD, ADD, LISTS }

data class HomeUiState(
    val tab: HomeTab = HomeTab.DASHBOARD,
    val query: String = "",
    val loading: Boolean = false,
    val candidates: List<LookupCandidate> = emptyList(),
    val activeProfile: LanguageProfileResponse? = null,
    val error: String? = null,
    val stats: DashboardStatsResponse? = null,
    val lists: List<WordListResponse> = emptyList(),
    val selectedListId: String? = null,
    val listWords: List<CardResponse> = emptyList(),
    val addTarget: LookupCandidate? = null,
    val pickListOpen: Boolean = false,
    val createListName: String = "",
    val showCreateListPrompt: Boolean = false,
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val repository: LearningRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(HomeUiState())
    val state: StateFlow<HomeUiState> = _state.asStateFlow()

    private var pollJob: Job? = null

    init {
        refreshAll()
    }

    fun refreshAll() {
        viewModelScope.launch {
            runCatching { repository.getActiveProfile() }
                .onSuccess { _state.value = _state.value.copy(activeProfile = it) }
            loadStats()
            loadLists()
        }
    }

    fun selectTab(tab: HomeTab) {
        _state.value = _state.value.copy(tab = tab, error = null)
        when (tab) {
            HomeTab.DASHBOARD -> loadStats()
            HomeTab.LISTS -> loadLists()
            HomeTab.ADD -> Unit
        }
    }

    /** Odśwież dashboard przy powrocie na Home (np. z Ćwicz) — liczby mają być aktualne. */
    fun onHomeResumed() {
        if (_state.value.tab == HomeTab.DASHBOARD) {
            loadStats()
        }
    }

    fun loadStats() {
        viewModelScope.launch {
            runCatching { repository.dashboardStats(7) }
                .onSuccess { _state.value = _state.value.copy(stats = it, error = null) }
                .onFailure {
                    runCatching {
                        val q = repository.getQueue()
                        val settings = repository.getSettings()
                        DashboardStatsResponse(
                            due_count = q.due.size,
                            new_remaining = (settings.new_cards_per_day - q.newCards.size).coerceAtLeast(0),
                            new_done_today = 0,
                            new_limit = settings.new_cards_per_day,
                            reviews_done_today = 0,
                            done_today = 0,
                            srs_new = q.newCards.size,
                            srs_due = q.due.size,
                            srs_learning = q.due.size,
                            srs_mastered = 0,
                            new_reserve = q.newCards.size,
                            cards_total = q.due.size + q.newCards.size,
                        )
                    }.onSuccess { _state.value = _state.value.copy(stats = it) }
                        .onFailure { e -> _state.value = _state.value.copy(error = e.userMessage("Błąd statystyk")) }
                }
        }
    }

    fun loadLists(selectId: String? = null) {
        viewModelScope.launch {
            runCatching { repository.listWordLists() }
                .onSuccess { lists ->
                    val selected = selectId
                        ?: _state.value.selectedListId
                        ?: lists.firstOrNull { it.is_system }?.id
                        ?: lists.firstOrNull()?.id
                    _state.value = _state.value.copy(lists = lists, selectedListId = selected)
                    selected?.let { loadListWords(it) }
                }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd list")) }
        }
    }

    fun selectList(listId: String) {
        _state.value = _state.value.copy(selectedListId = listId)
        loadListWords(listId)
    }

    fun openListTab(listId: String) {
        _state.value = _state.value.copy(tab = HomeTab.LISTS, selectedListId = listId, error = null)
        loadLists(listId)
    }

    fun openListFromChip(listId: String?, listName: String?) {
        val id = listId
            ?: _state.value.lists.firstOrNull { it.name == listName }?.id
            ?: return
        openListTab(id)
    }

    fun loadListWords(listId: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true)
            runCatching { repository.listWords(listId) }
                .onSuccess { words ->
                    _state.value = _state.value.copy(loading = false, listWords = words, error = null)
                    startPollingIfNeeded()
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        loading = false,
                        error = it.userMessage("Błąd słów listy"),
                    )
                }
        }
    }

    fun onQueryChange(value: String) {
        _state.value = _state.value.copy(query = value, error = null)
    }

    fun search() {
        val text = _state.value.query.trim()
        if (text.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null, tab = HomeTab.ADD)
            runCatching { repository.lookup(text) }
                .onSuccess { response ->
                    _state.value = _state.value.copy(
                        loading = false,
                        candidates = response.candidates,
                    )
                    startPollingIfNeeded()
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        loading = false,
                        error = it.userMessage("Błąd wyszukiwania"),
                    )
                }
        }
    }

    fun openAddSheet(candidate: LookupCandidate) {
        if (candidate.onList || candidate.isCreating) return
        _state.value = _state.value.copy(addTarget = candidate, pickListOpen = false, showCreateListPrompt = false)
    }

    fun dismissAddSheet() {
        _state.value = _state.value.copy(
            addTarget = null,
            pickListOpen = false,
            showCreateListPrompt = false,
            createListName = "",
        )
    }

    fun addToLearning() {
        val candidate = _state.value.addTarget ?: return
        val learning = _state.value.lists.firstOrNull { it.is_system }
        if (learning != null) {
            addToList(learning.id)
        } else {
            beginCreating(candidate, "Uczę się", null)
            viewModelScope.launch {
                runCatching {
                    repository.createCard(
                        candidate.lemma,
                        candidate.pos,
                        candidate.gloss,
                        candidate.lexical_entry_id,
                    )
                }.onSuccess { card ->
                    markCandidateOnList(
                        candidate,
                        "Uczę się",
                        null,
                        card.id,
                        card.enrichment_status,
                    )
                    loadLists()
                    startPollingIfNeeded()
                }.onFailure {
                    revertCreating(candidate)
                    _state.value = _state.value.copy(error = it.userMessage("Błąd dodawania"))
                }
            }
        }
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
        }
    }

    fun openCreateListPrompt() {
        _state.value = _state.value.copy(showCreateListPrompt = true, pickListOpen = true)
    }

    fun onCreateListNameChange(value: String) {
        _state.value = _state.value.copy(createListName = value)
    }

    fun createListAndAdd() {
        val name = _state.value.createListName.trim()
        if (name.isBlank()) return
        listNameConflictMessage(_state.value.lists, name)?.let {
            _state.value = _state.value.copy(error = it)
            return
        }
        val candidate = _state.value.addTarget ?: return
        beginCreating(candidate, name, null)
        viewModelScope.launch {
            runCatching {
                val list = repository.createWordList(name)
                repository.addWordToList(
                    list.id,
                    candidate.lemma,
                    candidate.pos,
                    candidate.gloss,
                    candidate.lexical_entry_id,
                ) to list
            }.onSuccess { (card, list) ->
                markCandidateOnList(
                    candidate,
                    list.name,
                    list.id,
                    card.id,
                    card.enrichment_status,
                )
                loadLists(list.id)
                startPollingIfNeeded()
            }.onFailure {
                revertCreating(candidate)
                _state.value = _state.value.copy(error = it.userMessage("Błąd tworzenia listy"))
            }
        }
    }

    fun addToList(listId: String) {
        val candidate = _state.value.addTarget ?: return
        val listName = _state.value.lists.firstOrNull { it.id == listId }?.name ?: "Lista"
        beginCreating(candidate, listName, listId)
        viewModelScope.launch {
            runCatching {
                repository.addWordToList(
                    listId,
                    candidate.lemma,
                    candidate.pos,
                    candidate.gloss,
                    candidate.lexical_entry_id,
                )
            }.onSuccess { card ->
                markCandidateOnList(
                    candidate,
                    listName,
                    listId,
                    card.id,
                    card.enrichment_status,
                )
                loadLists(listId)
                startPollingIfNeeded()
            }.onFailure {
                revertCreating(candidate)
                _state.value = _state.value.copy(error = it.userMessage("Błąd dodawania do listy"))
            }
        }
    }

    fun createEmptyList(name: String) {
        val trimmed = name.trim().ifBlank { return }
        listNameConflictMessage(_state.value.lists, trimmed)?.let {
            _state.value = _state.value.copy(error = it)
            return
        }
        viewModelScope.launch {
            runCatching { repository.createWordList(trimmed) }
                .onSuccess { list -> loadLists(list.id) }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd tworzenia listy")) }
        }
    }

    /** Tworzy listę i od razu przenosi na nią słowo. */
    fun createListAndMoveWord(name: String, cardId: String) {
        val trimmed = name.trim().ifBlank { return }
        listNameConflictMessage(_state.value.lists, trimmed)?.let {
            _state.value = _state.value.copy(error = it)
            return
        }
        viewModelScope.launch {
            runCatching {
                val list = repository.createWordList(trimmed)
                repository.moveCard(cardId, list.id)
                list
            }.onSuccess { list ->
                _state.value = _state.value.copy(
                    listWords = _state.value.listWords.filterNot { it.id == cardId },
                )
                loadLists(list.id)
            }.onFailure {
                _state.value = _state.value.copy(error = it.userMessage("Błąd tworzenia listy"))
            }
        }
    }

    fun renameList(listId: String, name: String) {
        val trimmed = name.trim().ifBlank { return }
        listNameConflictMessage(_state.value.lists, trimmed, excludeId = listId)?.let {
            _state.value = _state.value.copy(error = it)
            return
        }
        viewModelScope.launch {
            runCatching { repository.renameWordList(listId, trimmed) }
                .onSuccess { loadLists(listId) }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd zmiany nazwy")) }
        }
    }

    fun deleteList(listId: String) {
        viewModelScope.launch {
            runCatching { repository.deleteWordList(listId) }
                .onSuccess {
                    val fallback = _state.value.lists.firstOrNull { it.is_system }?.id
                    loadLists(fallback)
                }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd usuwania listy")) }
        }
    }

    fun deleteWord(cardId: String) {
        viewModelScope.launch {
            runCatching { repository.deleteCard(cardId) }
                .onSuccess {
                    _state.value = _state.value.copy(
                        listWords = _state.value.listWords.filterNot { it.id == cardId },
                        candidates = _state.value.candidates.map { c ->
                            if (c.learning_card_id == cardId) {
                                c.copy(
                                    in_learning = false,
                                    learning_card_id = null,
                                    list_id = null,
                                    list_name = null,
                                    enrichment_status = null,
                                )
                            } else c
                        },
                    )
                    loadLists(_state.value.selectedListId)
                }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd usuwania słowa")) }
        }
    }

    fun moveWord(cardId: String, targetListId: String) {
        viewModelScope.launch {
            runCatching { repository.moveCard(cardId, targetListId) }
                .onSuccess {
                    _state.value = _state.value.copy(
                        listWords = _state.value.listWords.filterNot { it.id == cardId },
                    )
                    loadLists(_state.value.selectedListId)
                }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd przenoszenia")) }
        }
    }

    private fun beginCreating(candidate: LookupCandidate, listName: String, listId: String?) {
        dismissAddSheet()
        val optimistic = CardResponse(
            id = "pending-${candidate.lemma}",
            lemma_l2 = candidate.lemma,
            pos = candidate.pos,
            gloss_primary = candidate.gloss,
            content = kotlinx.serialization.json.JsonObject(emptyMap()),
            created_at = "",
            enrichment_status = "pending",
        )
        val onCurrentList = listId == null || listId == _state.value.selectedListId
        _state.value = _state.value.copy(
            candidates = _state.value.candidates.map {
                if (it.lemma == candidate.lemma && it.pos == candidate.pos) {
                    it.copy(
                        in_learning = listName == "Uczę się",
                        list_id = listId,
                        list_name = listName,
                        enrichment_status = "pending",
                    )
                } else it
            },
            listWords = if (onCurrentList) {
                listOf(optimistic) + _state.value.listWords.filterNot {
                    it.lemma_l2.equals(candidate.lemma, ignoreCase = true) && it.pos == candidate.pos
                }
            } else {
                _state.value.listWords
            },
        )
    }

    private fun revertCreating(candidate: LookupCandidate) {
        _state.value = _state.value.copy(
            candidates = _state.value.candidates.map {
                if (it.lemma == candidate.lemma && it.pos == candidate.pos) {
                    it.copy(
                        in_learning = false,
                        learning_card_id = null,
                        list_id = null,
                        list_name = null,
                        enrichment_status = null,
                    )
                } else it
            },
            listWords = _state.value.listWords.filterNot { it.id.startsWith("pending-") && it.lemma_l2 == candidate.lemma },
        )
    }

    private fun markCandidateOnList(
        candidate: LookupCandidate,
        listName: String,
        listId: String?,
        cardId: String,
        enrichmentStatus: String,
    ) {
        _state.value = _state.value.copy(
            candidates = _state.value.candidates.map {
                if (it.lemma == candidate.lemma && it.pos == candidate.pos) {
                    it.copy(
                        in_learning = listName == "Uczę się",
                        learning_card_id = cardId,
                        list_id = listId,
                        list_name = listName,
                        enrichment_status = enrichmentStatus,
                    )
                } else it
            },
            listWords = _state.value.listWords.map {
                if (it.id.startsWith("pending-") && it.lemma_l2.equals(candidate.lemma, ignoreCase = true)) {
                    it.copy(id = cardId, enrichment_status = enrichmentStatus)
                } else it
            },
        )
    }

    private fun startPollingIfNeeded() {
        val pendingCandidates = _state.value.candidates.any { it.enrichment_status == "pending" }
        val pendingWords = _state.value.listWords.any { it.enrichment_status == "pending" }
        if (!pendingCandidates && !pendingWords) {
            pollJob?.cancel()
            return
        }
        if (pollJob?.isActive == true) return
        pollJob = viewModelScope.launch {
            while (isActive) {
                delay(2_500)
                val listId = _state.value.selectedListId
                if (listId != null) {
                    runCatching { repository.listWords(listId) }
                        .onSuccess { words ->
                            _state.value = _state.value.copy(listWords = words)
                            syncCandidatesFromWords(words)
                        }
                } else {
                    val query = _state.value.query.trim()
                    if (query.isNotBlank()) {
                        runCatching { repository.lookup(query) }
                            .onSuccess { response ->
                                _state.value = _state.value.copy(candidates = response.candidates)
                            }
                    }
                }
                val stillPending =
                    _state.value.candidates.any { it.enrichment_status == "pending" } ||
                        _state.value.listWords.any { it.enrichment_status == "pending" }
                if (!stillPending) break
            }
        }
    }

    private fun syncCandidatesFromWords(words: List<CardResponse>) {
        if (_state.value.candidates.isEmpty()) return
        val byLemma = words.associateBy { it.lemma_l2.lowercase() to it.pos }
        _state.value = _state.value.copy(
            candidates = _state.value.candidates.map { c ->
                val card = byLemma[c.lemma.lowercase() to c.pos]
                    ?: byLemma.entries.firstOrNull { it.key.first == c.lemma.lowercase() }?.value
                if (card == null) c else c.copy(
                    learning_card_id = card.id,
                    list_name = c.list_name ?: "Uczę się",
                    enrichment_status = card.enrichment_status,
                    in_learning = c.in_learning || c.list_name == "Uczę się",
                )
            },
        )
    }
}

internal fun listNameConflictMessage(
    lists: List<WordListResponse>,
    name: String,
    excludeId: String? = null,
): String? {
    val trimmed = name.trim()
    if (trimmed.isBlank()) return null
    if (trimmed.equals("Uczę się", ignoreCase = true)) return "Ta nazwa jest zarezerwowana"
    val taken = lists.any { it.id != excludeId && it.name.equals(trimmed, ignoreCase = true) }
    return if (taken) "Jest już lista o takiej nazwie" else null
}
