package com.vocabulario.app.ui.home

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.PairSession
import com.vocabulario.app.data.SYSTEM_LIST_NAME
import com.vocabulario.app.data.isReservedListName
import com.vocabulario.app.data.normalizePosKey
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.DashboardStatsResponse
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.api.WordListResponse
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.imports.ImportController
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.i18n.UiStrings
import com.vocabulario.app.ui.card.CorrectionResultItem
import com.vocabulario.app.ui.card.CorrectionResultsState
import com.vocabulario.app.ui.card.HomeUiStateSelfEditActive
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.debounce
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
    val notice: String? = null,
    val isOnline: Boolean = true,
    val stats: DashboardStatsResponse? = null,
    val lists: List<WordListResponse> = emptyList(),
    val selectedListId: String? = null,
    val listWords: List<CardResponse> = emptyList(),
    val addTarget: LookupCandidate? = null,
    val pickListOpen: Boolean = false,
    val createListName: String = "",
    val showCreateListPrompt: Boolean = false,
    /** Multi-select na liście słów. */
    val selectedWordIds: Set<String> = emptySet(),
    val listSortOrder: ListSortOrder = ListSortOrder.LemmaAsc,
    val listFilter: ListFilterState = ListFilterState(),
    val correctionCardId: String? = null,
    val correctionSubmitting: Boolean = false,
    val correctionResults: CorrectionResultsState = CorrectionResultsState(),
    val correctionQuotaRemaining: Int? = null,
    val selfEditCard: CardResponse? = null,
    val selfEditSaving: Boolean = false,
    val selfEditValidating: Boolean = false,
    val selfEditProgressCardId: String? = null,
    val selfEditPendingCardId: String? = null,
    val selfEditWarningOpen: Boolean = false,
    val selfEditValidationIssues: List<com.vocabulario.app.data.api.SelfEditValidateIssue> = emptyList(),
    val selfEditPendingContent: kotlinx.serialization.json.JsonObject? = null,
    val historyCardId: String? = null,
    val historyEvents: List<com.vocabulario.app.data.api.CardHistoryEventResponse> = emptyList(),
    val historyLoading: Boolean = false,
    val historyRestoring: Boolean = false,
    /** Po przejściu z lookup — rozwiń ten kafelek na liście. */
    val focusWordId: String? = null,
    val focusLemma: String? = null,
    // „Wymaga sprawdzenia" — modal dla słów bez pewnego dopasowania.
    val reviewCardId: String? = null,
    val reviewWord: String? = null,
    val reviewSuggestions: List<LookupCandidate> = emptyList(),
    val reviewSelectedIndex: Int? = null,
    val reviewLoading: Boolean = false,
    val reviewSubmitting: Boolean = false,
) {
    val selectionMode: Boolean get() = selectedWordIds.isNotEmpty()
    val visibleListWords: List<CardResponse>
        get() = applyListFilterSort(listWords, listFilter, listSortOrder)
    val hasMovableListWords: Boolean get() = listWords.any { it.isReadyToMove() }
    val hasMovableSelectedWords: Boolean
        get() = listWords.any { it.id in selectedWordIds && it.isReadyToMove() }
}

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val repository: LearningRepository,
    private val tokenStore: TokenStore,
    private val strings: UiStrings,
    private val networkMonitor: com.vocabulario.app.data.NetworkMonitor,
    private val pairSession: PairSession,
    private val importController: ImportController,
) : ViewModel() {

    private val _state = MutableStateFlow(HomeUiState(isOnline = networkMonitor.isCurrentlyOnline()))
    val state: StateFlow<HomeUiState> = _state.asStateFlow()

    val importState = importController.state

    /** Źródło prawdy o sieci — UI (zakładka „dodaj”) subskrybuje bezpośrednio, bez opóźnienia przez HomeUiState. */
    val connectivity: StateFlow<Boolean> = networkMonitor.isOnline

    private var pollJob: Job? = null
    private var boundProfileId: String? = null
    private var listsObserverJob: Job? = null
    private var cardsObserverJob: Job? = null
    private var roomRefreshJob: Job? = null
    /** Podczas move/delete nie publikuj pośrednich liczników z Room. */
    private var pauseRoomRefresh = false

    init {
        viewModelScope.launch { refreshAll() }
        viewModelScope.launch {
            importController.navigateToList.collect { listId ->
                openListTab(listId)
            }
        }
        viewModelScope.launch {
            var prev: com.vocabulario.app.data.imports.ImportStatus? = null
            var prevCreated = -1
            importController.state.collect { job ->
                val finished = job.status == com.vocabulario.app.data.imports.ImportStatus.Done ||
                    job.status == com.vocabulario.app.data.imports.ImportStatus.Failed
                val justFinished = finished && prev != job.status
                val createdMoved = job.createdCount != prevCreated && job.createdCount > 0
                if (justFinished || createdMoved) {
                    job.targetListId?.let { loadLists(it) } ?: loadLists()
                    if (justFinished) loadStats()
                }
                prev = job.status
                prevCreated = job.createdCount
            }
        }
        viewModelScope.launch {
            var firstEmission = true
            @OptIn(FlowPreview::class)
            networkMonitor.isOnline.debounce(800).collect { online ->
                val wasOffline = !_state.value.isOnline
                _state.value = _state.value.copy(
                    isOnline = online,
                    notice = if (online && wasOffline) null else _state.value.notice,
                    error = if (!online && _state.value.tab == HomeTab.ADD) null else _state.value.error,
                )
                if (firstEmission) {
                    firstEmission = false
                    return@collect
                }
                if (online && wasOffline) {
                    repository.requestBackgroundSync()
                }
            }
        }
        viewModelScope.launch {
            tokenStore.activeProfileId.collect { profileId ->
                if (profileId.isNullOrBlank()) return@collect
                if (profileId == boundProfileId) return@collect
                val firstBind = boundProfileId == null
                boundProfileId = profileId
                onLanguagePairChanged(wipeUi = !firstBind)
                startRoomObservers(profileId)
            }
        }
    }

    /**
     * Reaktywne odświeżanie: kiedy Room (listy/karty) zmieni się z dowolnego powodu
     * (mutacja lokalna, sync w tle, tombstone z innego urządzenia), UI odświeża się samo
     * — bez ręcznego wołania refreshAll w każdym miejscu. `distinctUntilChanged` w repo
     * odfiltrowuje re-zapisy tą samą treścią, więc nie ma pętli.
     */
    private fun startRoomObservers(profileId: String) {
        listsObserverJob?.cancel()
        cardsObserverJob?.cancel()
        listsObserverJob = viewModelScope.launch {
            repository.listsChanges(profileId).collect { scheduleRoomRefresh(profileId) }
        }
        cardsObserverJob = viewModelScope.launch {
            repository.cardsChanges(profileId).collect { scheduleRoomRefresh(profileId) }
        }
    }

    /** Jedno wspólne odświeżenie po zmianie Room — tylko cache, bez GET /lists. */
    private fun scheduleRoomRefresh(profileId: String) {
        if (pauseRoomRefresh) return
        roomRefreshJob?.cancel()
        roomRefreshJob = viewModelScope.launch {
            delay(250)
            if (pauseRoomRefresh || boundProfileId != profileId) return@launch
            publishListsFromCache(_state.value.selectedListId)
        }
    }

    private suspend fun withPausedRoomRefresh(block: suspend () -> Unit) {
        pauseRoomRefresh = true
        roomRefreshJob?.cancel()
        try {
            block()
        } finally {
            pauseRoomRefresh = false
        }
    }

    /** Jedna publikacja list + słów + liczników z Room. */
    private suspend fun publishListsFromCache(
        selectId: String? = null,
        clearSelection: Boolean = false,
    ) {
        val lists = runCatching { repository.cachedWordLists() }.getOrNull() ?: return
        if (lists.isEmpty() && _state.value.lists.isNotEmpty()) return
        val visible = visibleLists(lists)
        val requested = selectId
            ?: _state.value.selectedListId
            ?: visible.firstOrNull { it.is_system }?.id
            ?: visible.firstOrNull()?.id
        var selected = visible.firstOrNull { it.id == requested }?.id
            ?: visible.firstOrNull { it.is_system }?.id
            ?: visible.firstOrNull()?.id
        if (selected?.startsWith("local-pending-inbox-") == true) {
            selected = visible.firstOrNull { it.is_pending_inbox }?.id ?: selected
        } else if (
            requested != null &&
            requested.startsWith("local-pending-inbox-") &&
            visible.any { it.is_pending_inbox }
        ) {
            selected = visible.firstOrNull { it.is_pending_inbox }?.id
        }
        val words = selected?.let { runCatching { repository.cachedListWords(it) }.getOrNull() }
        val stats = runCatching { repository.dashboardStats(7) }.getOrNull()
        _state.value = _state.value.copy(
            loading = false,
            lists = visible,
            selectedListId = selected ?: _state.value.selectedListId,
            listWords = words ?: _state.value.listWords,
            selectedWordIds = if (clearSelection) emptySet() else _state.value.selectedWordIds,
            stats = stats ?: _state.value.stats,
        )
    }

    /** Drop pair-scoped UI state immediately, then reload lists/cards/stats. */
    private fun onLanguagePairChanged(wipeUi: Boolean = true) {
        pollJob?.cancel()
        if (wipeUi) {
            val keepTab = _state.value.tab
            val online = networkMonitor.isCurrentlyOnline()
            _state.value = HomeUiState(tab = keepTab, isOnline = online)
        }
        refreshAll()
    }

    fun clearNotice() {
        _state.value = _state.value.copy(notice = null)
    }

    fun refreshAll() {
        viewModelScope.launch {
            runCatching { repository.getActiveProfile() }
                .onSuccess { _state.value = _state.value.copy(activeProfile = it) }
            loadStats()
            loadLists()
            pairSession.markDataReady()
        }
    }
    fun selectTab(tab: HomeTab) {
        val leavingAdd = _state.value.tab == HomeTab.ADD && tab != HomeTab.ADD
        _state.value = _state.value.copy(
            tab = tab,
            error = null,
            selectedWordIds = if (tab != HomeTab.LISTS) emptySet() else _state.value.selectedWordIds,
            query = if (leavingAdd) "" else _state.value.query,
            candidates = if (leavingAdd) emptyList() else _state.value.candidates,
            addTarget = if (leavingAdd) null else _state.value.addTarget,
            pickListOpen = if (leavingAdd) false else _state.value.pickListOpen,
            showCreateListPrompt = if (leavingAdd) false else _state.value.showCreateListPrompt,
            createListName = if (leavingAdd) "" else _state.value.createListName,
        )
        when (tab) {
            HomeTab.DASHBOARD -> loadStats()
            HomeTab.LISTS -> loadLists()
            HomeTab.ADD -> Unit
        }
    }

    /** Odśwież dashboard przy powrocie na Home (np. z Ćwicz) — liczby mają być aktualne. */
    fun onHomeResumed() {
        importController.onAppForeground()
        if (_state.value.tab == HomeTab.DASHBOARD) {
            loadStats()
        }
    }

    fun expandImportSection(section: String?) = importController.expandSection(section)

    fun onImportErrorsCopied() = importController.copiedErrorsNotice()

    fun loadStats() {
        viewModelScope.launch {
            runCatching { repository.dashboardStats(7) }
                .onSuccess { _state.value = _state.value.copy(stats = it, error = null) }
                .onFailure { e ->
                    _state.value = _state.value.copy(
                        error = e.userMessage(strings, R.string.err_load_stats),
                    )
                }
        }
    }

    fun loadLists(selectId: String? = null) {
        viewModelScope.launch {
            runCatching { repository.listWordLists() }
                .onSuccess { lists ->
                    val visible = visibleLists(lists)
                    val requested = selectId
                        ?: _state.value.selectedListId
                        ?: visible.firstOrNull { it.is_system }?.id
                        ?: visible.firstOrNull()?.id
                    var selected = visible.firstOrNull { it.id == requested }?.id
                        ?: visible.firstOrNull { it.is_system }?.id
                        ?: visible.firstOrNull()?.id
                    // Po syncu lokalny local-pending-inbox-* → serwerowy UUID.
                    if (selected?.startsWith("local-pending-inbox-") == true) {
                        selected = visible.firstOrNull { it.is_pending_inbox }?.id ?: selected
                    } else if (
                        requested != null &&
                        requested.startsWith("local-pending-inbox-") &&
                        visible.any { it.is_pending_inbox }
                    ) {
                        selected = visible.firstOrNull { it.is_pending_inbox }?.id
                    }
                    // Czy ta sama lista jest już pokazana z kartami? Jeśli tak — odświeżamy w tle
                    // (bez pełnoekranowego spinnera, karty zostają na miejscu). Skrzynka Oczekujące
                    // zmienia id local-pending-inbox-* → serwerowy UUID, więc traktujemy oba jako tę samą.
                    val prevId = _state.value.selectedListId
                    val prevIsPendingInbox = prevId?.startsWith("local-pending-inbox-") == true ||
                        _state.value.lists.firstOrNull { it.id == prevId }?.is_pending_inbox == true
                    val newIsPendingInbox = visible.firstOrNull { it.id == selected }?.is_pending_inbox == true
                    val sameLogicalList = selected != null &&
                        (selected == prevId || (prevIsPendingInbox && newIsPendingInbox))
                    val backgroundRefresh = sameLogicalList && _state.value.listWords.isNotEmpty()
                    _state.value = _state.value.copy(lists = visible, selectedListId = selected)
                    selected?.let { loadListWords(it, background = backgroundRefresh) }
                }
                .onFailure {
                    _state.value = _state.value.copy(error = it.userMessage(strings, R.string.err_lists))
                }
        }
    }

    fun selectList(listId: String) {
        val switching = _state.value.selectedListId != listId
        _state.value = _state.value.copy(
            selectedListId = listId,
            selectedWordIds = emptySet(),
            listFilter = if (switching) ListFilterState() else _state.value.listFilter,
        )
        loadListWords(listId)
    }

    fun setListSortOrder(order: ListSortOrder) {
        _state.value = _state.value.copy(listSortOrder = order)
    }

    fun setListFilter(filter: ListFilterState) {
        _state.value = _state.value.copy(listFilter = filter)
    }

    fun clearListFilter() {
        _state.value = _state.value.copy(listFilter = ListFilterState())
    }

    fun openListTab(listId: String) {
        _state.value = _state.value.copy(
            tab = HomeTab.LISTS,
            selectedListId = listId,
            error = null,
        )
        loadLists(listId)
    }

    fun openListFromChip(listId: String?, listName: String?) {
        val id = listId
            ?: _state.value.lists.firstOrNull { it.name == listName }?.id
            ?: return
        openListTab(id)
    }

    fun openWordOnList(candidate: LookupCandidate) {
        if (!candidate.onList) return
        val lists = _state.value.lists
        val listId = candidate.list_id
            ?: lists.firstOrNull { list ->
                val name = candidate.list_name ?: return@firstOrNull false
                list.name == name || (isLearningListName(name) && list.is_system)
            }?.id
            ?: return
        _state.value = _state.value.copy(
            tab = HomeTab.LISTS,
            selectedListId = listId,
            focusWordId = candidate.learning_card_id,
            focusLemma = candidate.lemma.takeIf { candidate.learning_card_id.isNullOrBlank() },
            listFilter = ListFilterState(),
            selectedWordIds = emptySet(),
            error = null,
        )
        loadLists(listId)
    }

    fun clearWordFocus() {
        if (_state.value.focusWordId != null || _state.value.focusLemma != null) {
            _state.value = _state.value.copy(focusWordId = null, focusLemma = null)
        }
    }

    /**
     * @param background gdy true — odświeżamy już wyświetlaną listę BEZ pełnoekranowego spinnera.
     * Karty zostają na ekranie, a stan pojedynczej karty (np. „Tworzę kartę") pokazuje spinner
     * w samej karcie. Kluczowe przy powrocie online, żeby kafelki nie znikały pod jeden wielki spinner.
     */
    @Suppress("UNUSED_PARAMETER")
    fun loadListWords(listId: String, background: Boolean = false) {
        viewModelScope.launch {
            runCatching { repository.hydrateListIfEmpty(listId) }
                .onSuccess { words ->
                    _state.value = _state.value.copy(loading = false, listWords = words, error = null)
                    startPollingIfNeeded()
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        loading = false,
                        error = it.userMessage(strings, R.string.err_list_words),
                    )
                }

            val pendingInbox = _state.value.lists.find { it.id == listId }?.is_pending_inbox == true ||
                listId.startsWith("local-pending-inbox-")
            if (pendingInbox && networkMonitor.isCurrentlyOnline() &&
                runCatching { repository.hasQueuedLookups() }.getOrDefault(false)
            ) {
                runCatching { repository.flushPendingLookupsIfNeeded() }
                runCatching { repository.cachedListWords(listId) }
                    .onSuccess { words ->
                        _state.value = _state.value.copy(listWords = words, error = null)
                    }
            }
        }
    }

    fun onQueryChange(value: String) {
        _state.value = _state.value.copy(query = value, error = null, notice = null)
    }

    fun prepareVoiceSearch() {
        _state.value = _state.value.copy(
            query = "",
            candidates = emptyList(),
            error = null,
            notice = null,
        )
    }

    fun search() {
        if (importController.state.value.blocksUi) return
        val text = _state.value.query.trim()
        if (text.isBlank()) return
        if (!networkMonitor.isCurrentlyOnline()) {
            viewModelScope.launch {
                _state.value = _state.value.copy(loading = true, error = null, notice = null, tab = HomeTab.ADD)
                runCatching { repository.enqueueOfflineLookup(text) }
                    .onSuccess { added ->
                        _state.value = _state.value.copy(
                            loading = false,
                            query = "",
                            candidates = emptyList(),
                            notice = if (added) {
                                strings.get(R.string.offline_lookup_queued)
                            } else {
                                strings.get(R.string.offline_lookup_duplicate)
                            },
                        )
                        loadLists()
                    }
                    .onFailure {
                        _state.value = _state.value.copy(
                            loading = false,
                            error = it.userMessage(strings, R.string.err_search),
                        )
                    }
            }
            return
        }
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null, notice = null, tab = HomeTab.ADD)
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
                        error = it.userMessage(strings, R.string.err_search),
                    )
                }
        }
    }

    fun startImportFromFile(
        bytes: ByteArray,
        filename: String,
        mode: String,
        listId: String,
        listName: String,
    ) {
        importController.startFromFile(bytes, filename, mode, listId, listName)
    }

    fun startImportFromPaste(
        text: String,
        mode: String,
        listId: String,
        listName: String,
    ) {
        importController.startFromPaste(text, mode, listId, listName)
    }

    fun requestImportCancel() = importController.requestCancel()

    fun dismissImportAbortConfirm() = importController.dismissAbortConfirm()

    fun confirmImportCancel() = importController.confirmCancel()

    fun confirmImportCommit() = importController.confirmCommit()

    fun dismissImportResult(openList: Boolean = false) =
        importController.dismissResult(openList)

    fun setImportError(message: String) = importController.setUiError(message)

    /** Creates a list (if needed) then starts import. */
    fun startImportWithOptionalNewList(
        bytes: ByteArray?,
        filename: String?,
        pasteText: String?,
        mode: String,
        listId: String?,
        newListName: String?,
    ) {
        viewModelScope.launch {
            val resolved = resolveImportTarget(listId, newListName) ?: return@launch
            when {
                bytes != null && filename != null ->
                    importController.startFromFile(bytes, filename, mode, resolved.first, resolved.second)
                !pasteText.isNullOrBlank() ->
                    importController.startFromPaste(pasteText, mode, resolved.first, resolved.second)
            }
        }
    }

    private suspend fun resolveImportTarget(
        listId: String?,
        newListName: String?,
    ): Pair<String, String>? {
        val name = newListName?.trim().orEmpty()
        if (name.isNotBlank()) {
            listNameConflictMessage(strings, _state.value.lists, name)?.let {
                _state.value = _state.value.copy(error = it)
                return null
            }
            return runCatching { repository.createWordList(name) }
                .onSuccess { list ->
                    loadLists(list.id)
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_create_list),
                    )
                }
                .getOrNull()
                ?.let { it.id to it.name }
        }
        val id = listId ?: return null
        val list = _state.value.lists.firstOrNull { it.id == id } ?: return null
        val display = when {
            list.is_system -> strings.get(R.string.list_learning)
            list.is_pending_inbox -> strings.get(R.string.list_pending)
            else -> list.name
        }
        return id to display
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
            val learningLabel = strings.get(R.string.list_learning)
            beginCreating(candidate, learningLabel, null)
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
                        learningLabel,
                        null,
                        card.id,
                        card.enrichment_status,
                    )
                    loadLists()
                    startPollingIfNeeded()
                }.onFailure {
                    revertCreating(candidate)
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_add),
                    )
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
                        showCreateListPrompt = false,
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

    fun createListAndAdd() {
        val name = _state.value.createListName.trim()
        if (name.isBlank()) return
        listNameConflictMessage(strings, _state.value.lists, name)?.let {
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
                _state.value = _state.value.copy(
                    error = it.userMessage(strings, R.string.err_create_list),
                )
            }
        }
    }

    fun addToList(listId: String) {
        val candidate = _state.value.addTarget ?: return
        val list = _state.value.lists.firstOrNull { it.id == listId }
        val listName = when {
            list == null -> strings.get(R.string.list_fallback)
            list.is_system || list.name.equals(SYSTEM_LIST_NAME, ignoreCase = true) ->
                strings.get(R.string.list_learning)
            list.is_pending_inbox -> strings.get(R.string.list_pending)
            else -> list.name
        }
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
                _state.value = _state.value.copy(
                    error = it.userMessage(strings, R.string.err_add_to_list),
                )
            }
        }
    }

    fun createEmptyList(name: String) {
        val trimmed = name.trim().ifBlank { return }
        listNameConflictMessage(strings, _state.value.lists, trimmed)?.let {
            _state.value = _state.value.copy(error = it)
            return
        }
        viewModelScope.launch {
            runCatching { repository.createWordList(trimmed) }
                .onSuccess { list -> loadLists(list.id) }
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_create_list),
                    )
                }
        }
    }

    /** Tworzy listę i od razu przenosi na nią słowo. */
    fun createListAndMoveWord(name: String, cardId: String) {
        val trimmed = name.trim().ifBlank { return }
        listNameConflictMessage(strings, _state.value.lists, trimmed)?.let {
            _state.value = _state.value.copy(error = it)
            return
        }
        if (!isMovableCardId(cardId)) return
        createListAndMove(trimmed, listOf(cardId))
    }

    fun renameList(listId: String, name: String) {
        val trimmed = name.trim().ifBlank { return }
        listNameConflictMessage(strings, _state.value.lists, trimmed, excludeId = listId)?.let {
            _state.value = _state.value.copy(error = it)
            return
        }
        viewModelScope.launch {
            runCatching { repository.renameWordList(listId, trimmed) }
                .onSuccess { loadLists(listId) }
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_rename),
                    )
                }
        }
    }

    fun deleteList(listId: String) {
        val list = _state.value.lists.find { it.id == listId }
        if (list?.is_pending_inbox == true) {
            viewModelScope.launch {
                pollJob?.cancel()
                runCatching { repository.clearPendingInbox(listId) }
                    .onSuccess {
                        val fallback = _state.value.lists.firstOrNull { it.is_system }?.id
                        _state.value = _state.value.copy(
                            selectedWordIds = emptySet(),
                            listWords = emptyList(),
                            selectedListId = fallback,
                        )
                        loadLists(fallback)
                    }
                    .onFailure {
                        _state.value = _state.value.copy(
                            error = it.userMessage(strings, R.string.err_delete_list),
                        )
                    }
            }
            return
        }
        viewModelScope.launch {
            runCatching { repository.deleteWordList(listId) }
                .onSuccess {
                    val fallback = _state.value.lists.firstOrNull { it.is_system }?.id
                    loadLists(fallback)
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_delete_list),
                    )
                }
        }
    }

    fun deleteWord(cardId: String) {
        val sourceListId = _state.value.selectedListId
        viewModelScope.launch {
            withPausedRoomRefresh {
                val result = if (cardId.startsWith("pending-lookup-")) {
                    runCatching { repository.removePendingLookupStub(cardId) }
                } else {
                    runCatching { repository.deleteCard(cardId) }
                }
                result.onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_delete_word),
                    )
                    return@withPausedRoomRefresh
                }
                _state.value = _state.value.copy(
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
                publishListsFromCache(sourceListId, clearSelection = true)
            }
        }
    }

    /** Otwiera modal „wymaga sprawdzenia" dla stuba i ładuje zapisane propozycje. */
    fun openPendingReview(cardId: String) {
        _state.value = _state.value.copy(
            reviewCardId = cardId,
            reviewLoading = true,
            reviewSelectedIndex = null,
            reviewSuggestions = emptyList(),
            reviewWord = null,
        )
        viewModelScope.launch {
            val word = runCatching { repository.pendingReviewWord(cardId) }.getOrNull()
            val suggestions = runCatching { repository.pendingReviewSuggestions(cardId) }
                .getOrDefault(emptyList())
            if (_state.value.reviewCardId != cardId) return@launch
            _state.value = _state.value.copy(
                reviewWord = word,
                reviewSuggestions = suggestions,
                reviewLoading = false,
            )
        }
    }

    fun closePendingReview() {
        _state.value = _state.value.copy(
            reviewCardId = null,
            reviewWord = null,
            reviewSuggestions = emptyList(),
            reviewSelectedIndex = null,
            reviewLoading = false,
            reviewSubmitting = false,
        )
    }

    fun selectReviewSuggestion(index: Int) {
        _state.value = _state.value.copy(reviewSelectedIndex = index)
    }

    /** Odrzuca słowo — kasuje stub całkowicie i zamyka modal. */
    fun rejectReviewWord() {
        val cardId = _state.value.reviewCardId ?: return
        viewModelScope.launch {
            runCatching { repository.rejectPendingReview(cardId) }
                .onSuccess {
                    _state.value = _state.value.copy(
                        listWords = _state.value.listWords.filterNot { it.id == cardId },
                    )
                    closePendingReview()
                    loadLists(_state.value.selectedListId)
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_delete_word),
                        reviewSubmitting = false,
                    )
                }
        }
    }

    /** „Szukaj ponownie" — przenosi do zakładki Dodaj z wpisanym słowem, bez uruchamiania szukania. */
    fun retryReviewSearch() {
        val word = _state.value.reviewWord.orEmpty()
        closePendingReview()
        _state.value = _state.value.copy(
            tab = HomeTab.ADD,
            query = word,
            candidates = emptyList(),
            error = null,
        )
    }

    /** Zatwierdza zaznaczoną propozycję — dodaje kartę (enrichment) i zamyka modal. */
    fun approveReviewWord() {
        val cardId = _state.value.reviewCardId ?: return
        val index = _state.value.reviewSelectedIndex ?: return
        val candidate = _state.value.reviewSuggestions.getOrNull(index) ?: return
        // 1) Zamknij modal i podmień kafelek NATYCHMIAST (bez czekania na sieć).
        //    Optymistyczna karta: ta sama zaznaczona propozycja, status pending + spinner „Tworzę kartę".
        val optimistic = CardResponse(
            id = cardId,
            lemma_l2 = candidate.lemma,
            pos = candidate.pos,
            gloss_primary = candidate.gloss.takeIf { it.isNotBlank() },
            content = kotlinx.serialization.json.JsonObject(emptyMap()),
            lexical_entry_id = candidate.lexical_entry_id,
            created_at = "",
            persisted = false,
            enrichment_status = "pending",
        )
        closePendingReview()
        _state.value = _state.value.copy(
            listWords = _state.value.listWords.map { if (it.id == cardId) optimistic else it },
        )
        // 2) Sieć w tle.
        viewModelScope.launch {
            runCatching { repository.approvePendingReview(cardId, candidate) }
                .onSuccess {
                    _state.value.selectedListId?.let { loadListWords(it, background = true) }
                    loadLists(_state.value.selectedListId)
                    startPollingIfNeeded()
                }
                .onFailure {
                    // Cofnij optymistyczny kafelek i pokaż błąd.
                    _state.value = _state.value.copy(
                        listWords = _state.value.listWords.filterNot { it.id == cardId },
                        error = it.userMessage(strings, R.string.err_add_to_list),
                    )
                }
        }
    }

    fun moveWord(cardId: String, targetListId: String) {
        if (!isMovableCardId(cardId)) return
        commitMove(listOf(cardId), targetListId, selectTarget = false)
    }

    fun clearWordSelection() {
        _state.value = _state.value.copy(selectedWordIds = emptySet())
    }

    fun startWordSelection(cardId: String) {
        if (!isSelectableCardId(cardId)) return
        _state.value = _state.value.copy(selectedWordIds = setOf(cardId))
    }

    fun toggleWordSelection(cardId: String) {
        if (!isSelectableCardId(cardId)) return
        val cur = _state.value.selectedWordIds
        _state.value = _state.value.copy(
            selectedWordIds = if (cardId in cur) cur - cardId else cur + cardId,
        )
    }

    fun deleteSelectedWords() {
        val ids = _state.value.selectedWordIds.filter { isSelectableCardId(it) }
        if (ids.isEmpty()) return
        clearWordsByIds(ids)
    }

    fun clearAllWordsFromCurrentList() {
        val ids = _state.value.listWords.filter { it.isSelectableOnList() }.map { it.id }
        if (ids.isEmpty()) return
        clearWordsByIds(ids)
    }

    private fun clearWordsByIds(ids: List<String>) {
        val sourceListId = _state.value.selectedListId
        _state.value = _state.value.copy(selectedWordIds = emptySet())
        viewModelScope.launch {
            withPausedRoomRefresh {
                runCatching { repository.deleteCards(ids) }
                    .onFailure {
                        _state.value = _state.value.copy(
                            error = strings.get(R.string.err_delete_partial, ids.size),
                        )
                    }
                publishListsFromCache(sourceListId, clearSelection = true)
            }
        }
    }

    fun moveSelectedWords(targetListId: String) {
        val ids = _state.value.selectedWordIds.filter { isMovableCardId(it) }
        if (ids.isEmpty()) return
        commitMove(ids, targetListId)
    }

    fun moveAllWordsFromCurrentList(targetListId: String) {
        val ids = movableCardIds()
        if (ids.isEmpty()) return
        commitMove(ids, targetListId)
    }

    fun createListAndMoveSelected(name: String) {
        val trimmed = name.trim().ifBlank { return }
        listNameConflictMessage(strings, _state.value.lists, trimmed)?.let {
            _state.value = _state.value.copy(error = it)
            return
        }
        val ids = _state.value.selectedWordIds.filter { isMovableCardId(it) }
        if (ids.isEmpty()) return
        createListAndMove(trimmed, ids)
    }

    fun createListAndMoveAll(name: String) {
        val trimmed = name.trim().ifBlank { return }
        listNameConflictMessage(strings, _state.value.lists, trimmed)?.let {
            _state.value = _state.value.copy(error = it)
            return
        }
        val ids = movableCardIds()
        if (ids.isEmpty()) return
        createListAndMove(trimmed, ids)
    }

    private fun createListAndMove(name: String, ids: List<String>) {
        viewModelScope.launch {
            withPausedRoomRefresh {
                runCatching {
                    val list = repository.createWordList(name)
                    repository.moveCards(ids, list.id)
                    list
                }.onSuccess { list ->
                    publishListsFromCache(list.id, clearSelection = true)
                }.onFailure {
                    _state.value = _state.value.copy(
                        error = it.userMessage(strings, R.string.err_create_list),
                    )
                }
            }
        }
    }

    private fun commitMove(ids: List<String>, targetListId: String, selectTarget: Boolean = true) {
        val sourceId = _state.value.selectedListId
        _state.value = _state.value.copy(selectedWordIds = emptySet())
        viewModelScope.launch {
            withPausedRoomRefresh {
                runCatching { repository.moveCards(ids, targetListId) }
                    .onFailure {
                        _state.value = _state.value.copy(
                            error = it.userMessage(strings, R.string.err_move),
                        )
                    }
                val leftover = sourceId?.let {
                    runCatching { repository.cachedListWords(it) }.getOrNull()
                }.orEmpty()
                val sourceIsPending = _state.value.lists.any { it.id == sourceId && it.is_pending_inbox }
                val stayOnSource = !selectTarget ||
                    (sourceIsPending && leftover.any { !it.isReadyToMove() })
                publishListsFromCache(
                    if (stayOnSource) sourceId else targetListId,
                    clearSelection = true,
                )
            }
        }
    }

    private fun isMovableCard(card: CardResponse): Boolean = card.isReadyToMove()

    private fun isMovableCardId(cardId: String): Boolean {
        val card = _state.value.listWords.find { it.id == cardId } ?: return false
        return isMovableCard(card)
    }

    private fun isSelectableCardId(cardId: String): Boolean {
        val card = _state.value.listWords.find { it.id == cardId } ?: return true
        return card.isSelectableOnList()
    }

    private fun movableCardIds(): List<String> =
        _state.value.listWords.filter { isMovableCard(it) }.map { it.id }

    private fun isLearningListName(listName: String): Boolean =
        listName.equals(SYSTEM_LIST_NAME, ignoreCase = true) ||
            listName == strings.get(R.string.list_learning)

    private fun beginCreating(candidate: LookupCandidate, listName: String, listId: String?) {
        dismissAddSheet()
        val optimistic = CardResponse(
            id = pendingCardId(candidate.lemma, candidate.pos),
            lemma_l2 = candidate.lemma,
            pos = candidate.pos,
            gloss_primary = candidate.gloss,
            content = kotlinx.serialization.json.JsonObject(emptyMap()),
            lexical_entry_id = candidate.lexical_entry_id,
            created_at = "",
            enrichment_status = "pending",
        )
        val onCurrentList = listId == null || listId == _state.value.selectedListId
        _state.value = _state.value.copy(
            candidates = _state.value.candidates.map {
                if (sameLemmaAndPos(it.lemma, it.pos, candidate.lemma, candidate.pos)) {
                    it.copy(
                        in_learning = isLearningListName(listName),
                        list_id = listId,
                        list_name = listName,
                        enrichment_status = "pending",
                    )
                } else it
            },
            listWords = if (onCurrentList) {
                listOf(optimistic) + _state.value.listWords.filterNot {
                    sameLemmaAndPos(it.lemma_l2, it.pos, candidate.lemma, candidate.pos)
                }
            } else {
                _state.value.listWords
            },
        )
    }

    private fun revertCreating(candidate: LookupCandidate) {
        _state.value = _state.value.copy(
            candidates = _state.value.candidates.map {
                if (sameLemmaAndPos(it.lemma, it.pos, candidate.lemma, candidate.pos)) {
                    it.copy(
                        in_learning = false,
                        learning_card_id = null,
                        list_id = null,
                        list_name = null,
                        enrichment_status = null,
                    )
                } else it
            },
            listWords = _state.value.listWords.filterNot {
                it.id.startsWith("pending-") && sameLemmaAndPos(it.lemma_l2, it.pos, candidate.lemma, candidate.pos)
            },
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
                if (sameLemmaAndPos(it.lemma, it.pos, candidate.lemma, candidate.pos)) {
                    it.copy(
                        in_learning = isLearningListName(listName),
                        learning_card_id = cardId,
                        list_id = listId,
                        list_name = listName,
                        enrichment_status = enrichmentStatus,
                    )
                } else it
            },
            listWords = _state.value.listWords.map {
                if (it.id.startsWith("pending-") &&
                    sameLemmaAndPos(it.lemma_l2, it.pos, candidate.lemma, candidate.pos)
                ) {
                    it.copy(id = cardId, enrichment_status = enrichmentStatus)
                } else it
            },
        )
    }

    /**
     * Polling TYLKO obserwuje serwerowy enrichment (pending → ready). NIE wywołuje flushu —
     * flush leci dokładnie raz (przy wejściu na listę / przejściu online), serializowany mutexem
     * w repo. Dzięki temu nie ma lawiny zapytań LLM ani duplikatów kart.
     */
    private fun startPollingIfNeeded() {
        val pendingCandidates = _state.value.candidates.any { it.enrichment_status == "pending" }
        val pendingWords = _state.value.listWords.any { it.enrichment_status == "pending" }
        val hasActivity = _state.value.listWords.any { !it.card_activity_status.isNullOrBlank() }
        if (!pendingCandidates && !pendingWords && !hasActivity) {
            pollJob?.cancel()
            return
        }
        if (pollJob?.isActive == true) return
        repository.requestBackgroundSync()
        pollJob = viewModelScope.launch {
            var iterations = 0
            while (isActive) {
                delay(2_500)
                if (++iterations > 40) break
                val listId = _state.value.selectedListId
                if (listId != null) {
                    runCatching { repository.refreshListWordsFromServer(listId) }
                        .onSuccess { words ->
                            _state.value = _state.value.copy(listWords = words)
                            syncCandidatesFromWords(words)
                        }
                }
                val stillPending =
                    _state.value.candidates.any { it.enrichment_status == "pending" } ||
                        _state.value.listWords.any { it.enrichment_status == "pending" } ||
                        _state.value.listWords.any { !it.card_activity_status.isNullOrBlank() }
                if (!stillPending) {
                    runCatching { repository.evaluateReadyBatches() }
                    break
                }
            }
        }
    }

    private fun maybeStartActivityPoll() {
        startPollingIfNeeded()
    }

    private fun markCardActivity(cardId: String, status: String) {
        _state.value = _state.value.copy(
            listWords = _state.value.listWords.map { card ->
                if (card.id == cardId) card.copy(card_activity_status = status) else card
            },
        )
        maybeStartActivityPoll()
    }

    fun openCorrection(cardId: String) {
        if (!networkMonitor.isCurrentlyOnline()) {
            _state.value = _state.value.copy(error = strings.get(R.string.correction_requires_online))
            return
        }
        viewModelScope.launch {
            val remaining = runCatching { repository.correctionQuota() }.getOrNull()?.remaining
            _state.value = _state.value.copy(
                correctionCardId = cardId,
                correctionQuotaRemaining = remaining,
            )
        }
    }

    fun dismissCorrectionReport() {
        _state.value = _state.value.copy(
            correctionCardId = null,
            correctionSubmitting = false,
            correctionQuotaRemaining = null,
        )
    }

    fun openSelfEditFromReport() {
        val cardId = _state.value.correctionCardId ?: return
        val card = _state.value.listWords.firstOrNull { it.id == cardId }
        _state.value = _state.value.copy(
            correctionCardId = null,
            correctionSubmitting = false,
            selfEditCard = card,
        )
    }

    fun submitCorrection(sections: List<String>, note: String) {
        val cardId = _state.value.correctionCardId ?: return
        if (!networkMonitor.isCurrentlyOnline()) {
            _state.value = _state.value.copy(
                error = strings.get(R.string.correction_requires_online),
                correctionSubmitting = false,
            )
            return
        }
        viewModelScope.launch {
            _state.value = _state.value.copy(correctionSubmitting = true, error = null)
            runCatching {
                repository.submitCardCorrection(cardId, sections, note)
            }.onSuccess {
                _state.value = _state.value.copy(
                    correctionSubmitting = false,
                    correctionCardId = null,
                )
                markCardActivity(cardId, "correction_processing")
                pollCorrectionResult(cardId)
            }.onFailure { e ->
                _state.value = _state.value.copy(
                    correctionSubmitting = false,
                    error = e.userMessage(strings, R.string.err_save),
                )
            }
        }
    }

    private fun selfEditFlowActive(state: HomeUiState = _state.value): Boolean =
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

    private fun pollCorrectionResult(cardId: String) {
        viewModelScope.launch {
            repeat(10) {
                kotlinx.coroutines.delay(2_000)
                val latest = runCatching { repository.latestCardCorrection(cardId) }.getOrNull()
                if (latest != null && latest.status != "reported") {
                    val lemma = _state.value.listWords.firstOrNull { it.id == cardId }?.lemma_l2 ?: "—"
                    deliverCorrectionResult(latest, lemma)
                    repository.syncNow(fullReplace = false)
                    _state.value.selectedListId?.let { loadListWords(it, background = true) }
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
        val cardId = _state.value.correctionResults.active?.correction?.card_id ?: return
        val card = _state.value.listWords.firstOrNull { it.id == cardId }
        _state.value = _state.value.copy(
            correctionResults = _state.value.correctionResults.clearActiveForSelfEdit(),
            selfEditCard = card,
        )
    }

    fun openSelfEdit(card: CardResponse) {
        _state.value = _state.value.copy(selfEditCard = card)
    }

    fun dismissSelfEdit() {
        _state.value = _state.value.copy(
            selfEditCard = null,
            selfEditSaving = false,
            selfEditProgressCardId = null,
            selfEditPendingCardId = null,
            selfEditWarningOpen = false,
            selfEditValidationIssues = emptyList(),
            selfEditPendingContent = null,
        )
        maybeShowNextCorrectionResult()
    }

    fun saveSelfEdit(content: kotlinx.serialization.json.JsonObject) {
        val card = _state.value.selfEditCard ?: return
        val cardId = card.id
        viewModelScope.launch {
            _state.value = _state.value.copy(
                selfEditCard = null,
                selfEditProgressCardId = cardId,
                focusWordId = cardId,
                focusLemma = null,
                error = null,
            )
            runCatching {
                repository.validateSelfEdit(cardId, content)
            }.onSuccess { validation ->
                if (validation.ok) {
                    commitSelfEdit(cardId, content)
                } else {
                    _state.value = _state.value.copy(
                        selfEditProgressCardId = null,
                        selfEditWarningOpen = true,
                        selfEditValidationIssues = validation.issues,
                        selfEditPendingContent = content,
                        selfEditPendingCardId = cardId,
                    )
                }
            }.onFailure { e ->
                _state.value = _state.value.copy(
                    selfEditProgressCardId = null,
                    error = e.userMessage(strings, R.string.err_save),
                )
            }
        }
    }

    fun confirmSelfEditWarning() {
        val cardId = _state.value.selfEditPendingCardId ?: return
        val content = _state.value.selfEditPendingContent ?: return
        viewModelScope.launch {
            _state.value = _state.value.copy(
                selfEditWarningOpen = false,
                selfEditProgressCardId = cardId,
                focusWordId = cardId,
            )
            commitSelfEdit(cardId, content)
        }
    }

    fun revertSelfEditWarning() {
        dismissSelfEdit()
    }

    private suspend fun commitSelfEdit(cardId: String, content: kotlinx.serialization.json.JsonObject) {
        _state.value = _state.value.copy(
            selfEditSaving = true,
            selfEditWarningOpen = false,
            selfEditValidationIssues = emptyList(),
            selfEditPendingContent = null,
            selfEditPendingCardId = null,
        )
        runCatching {
            repository.selfEditCard(cardId, content)
        }.onSuccess { updated ->
            _state.value = _state.value.copy(
                selfEditSaving = false,
                selfEditProgressCardId = null,
            )
            _state.value = _state.value.copy(
                listWords = _state.value.listWords.map { c ->
                    if (c.id == updated.id) updated else c
                },
            )
            maybeStartActivityPoll()
            _state.value.selectedListId?.let { loadListWords(it, background = true) }
            maybeShowNextCorrectionResult()
        }.onFailure { e ->
            _state.value = _state.value.copy(
                selfEditSaving = false,
                selfEditProgressCardId = null,
                error = e.userMessage(strings, R.string.err_save),
            )
            maybeShowNextCorrectionResult()
        }
    }

    fun openCardHistory(cardId: String) {
        if (!networkMonitor.isCurrentlyOnline()) {
            _state.value = _state.value.copy(error = strings.get(R.string.correction_requires_online))
            return
        }
        _state.value = _state.value.copy(historyCardId = cardId, historyLoading = true, historyEvents = emptyList())
        viewModelScope.launch {
            runCatching { repository.getCardHistory(cardId) }
                .onSuccess { response ->
                    _state.value = _state.value.copy(
                        historyEvents = response.events,
                        historyLoading = false,
                    )
                }
                .onFailure { e ->
                    _state.value = _state.value.copy(
                        historyLoading = false,
                        historyCardId = null,
                        error = e.userMessage(strings, R.string.err_load_cards),
                    )
                }
        }
    }

    fun dismissCardHistory() {
        _state.value = _state.value.copy(
            historyCardId = null,
            historyEvents = emptyList(),
            historyLoading = false,
            historyRestoring = false,
        )
    }

    fun restoreFromHistory(eventId: String) {
        val cardId = _state.value.historyCardId ?: return
        viewModelScope.launch {
            _state.value = _state.value.copy(historyRestoring = true, error = null)
            runCatching { repository.restoreCard(cardId, eventId) }
                .onSuccess {
                    _state.value = _state.value.copy(historyRestoring = false)
                    dismissCardHistory()
                    _state.value.selectedListId?.let { loadListWords(it, background = true) }
                }
                .onFailure { e ->
                    _state.value = _state.value.copy(
                        historyRestoring = false,
                        error = e.userMessage(strings, R.string.err_save),
                    )
                }
        }
    }

    private fun syncCandidatesFromWords(words: List<CardResponse>) {
        if (_state.value.candidates.isEmpty()) return
        val learningLabel = strings.get(R.string.list_learning)
        _state.value = _state.value.copy(
            candidates = _state.value.candidates.map { c ->
                val card = words.firstOrNull { candidateMatchesCard(c, it) }
                if (card == null) c else {
                    val rawName = c.list_name
                    val displayName = when {
                        rawName == null -> learningLabel
                        rawName.equals(SYSTEM_LIST_NAME, ignoreCase = true) -> learningLabel
                        else -> rawName
                    }
                    c.copy(
                        learning_card_id = card.id,
                        list_name = displayName,
                        enrichment_status = card.enrichment_status,
                        in_learning = c.in_learning || isLearningListName(rawName ?: SYSTEM_LIST_NAME),
                    )
                }
            },
        )
    }

    private fun visibleLists(lists: List<WordListResponse>) =
        lists.filter { !it.is_pending_inbox || it.word_count > 0 }
}

internal fun pendingCardId(lemma: String, pos: String?): String =
    "pending-${lemma.trim().lowercase()}-${normalizePosKey(pos)}"

internal fun sameLemmaAndPos(
    lemmaA: String?,
    posA: String?,
    lemmaB: String?,
    posB: String?,
): Boolean {
    if (lemmaA.isNullOrBlank() || lemmaB.isNullOrBlank()) return false
    if (!lemmaA.equals(lemmaB, ignoreCase = true)) return false
    val a = normalizePosKey(posA)
    val b = normalizePosKey(posB)
    if (a == "unknown" || b == "unknown") return false
    return a == b
}

/** Ten sam lemat w innym POS to inna karta — nie zlewaj play/verb z play/noun. */
internal fun candidateMatchesCard(candidate: LookupCandidate, card: CardResponse): Boolean {
    return sameLemmaAndPos(card.lemma_l2, card.pos, candidate.lemma, candidate.pos)
}

internal fun listNameConflictMessage(
    strings: UiStrings,
    lists: List<WordListResponse>,
    name: String,
    excludeId: String? = null,
): String? {
    val trimmed = name.trim()
    if (trimmed.isBlank()) return null
    val pendingLabel = strings.get(R.string.list_pending)
    if (isReservedListName(trimmed, pendingLabel)) {
        return strings.get(R.string.list_name_reserved)
    }
    val taken = lists.any { it.id != excludeId && it.name.equals(trimmed, ignoreCase = true) }
    return if (taken) strings.get(R.string.list_name_taken) else null
}

internal fun listNameConflictMessage(
    context: Context,
    lists: List<WordListResponse>,
    name: String,
    excludeId: String? = null,
): String? {
    val trimmed = name.trim()
    if (trimmed.isBlank()) return null
    val pendingLabel = context.getString(R.string.list_pending)
    if (isReservedListName(trimmed, pendingLabel)) {
        return context.getString(R.string.list_name_reserved)
    }
    val taken = lists.any { it.id != excludeId && it.name.equals(trimmed, ignoreCase = true) }
    return if (taken) context.getString(R.string.list_name_taken) else null
}

internal fun isReservedListNameMessage(
    context: Context,
    name: String,
): Boolean {
    val trimmed = name.trim()
    if (trimmed.isBlank()) return false
    return isReservedListName(trimmed, context.getString(R.string.list_pending))
}
