package com.vocabulario.app.data.imports

import com.vocabulario.app.R
import com.vocabulario.app.data.BlockingBusy
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.NetworkMonitor
import com.vocabulario.app.data.api.ImportJobProgressResponse
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.sync.BackgroundJobScheduler
import com.vocabulario.app.i18n.UiStrings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import retrofit2.HttpException
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ImportController @Inject constructor(
    private val repository: LearningRepository,
    private val persistence: ImportStatePersistence,
    private val strings: UiStrings,
    private val networkMonitor: NetworkMonitor,
    private val backgroundJobs: BackgroundJobScheduler,
    private val blockingBusy: BlockingBusy,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    private val _state = MutableStateFlow(ImportJobState())
    val state: StateFlow<ImportJobState> = _state.asStateFlow()

    private val _navigateToList = MutableSharedFlow<String>(extraBufferCapacity = 1)
    val navigateToList: SharedFlow<String> = _navigateToList.asSharedFlow()

    private var pollJob: Job? = null

    init {
        scope.launch { restore() }
    }

    fun startFromFile(
        bytes: ByteArray,
        filename: String,
        mode: String,
        listId: String,
        listName: String,
    ) {
        if (_state.value.blocksUi) return
        if (!networkMonitor.isCurrentlyOnline()) {
            publishLocalError(strings.get(R.string.import_online_only))
            return
        }
        if (bytes.isEmpty()) {
            publishLocalError(strings.get(R.string.err_import_empty_file))
            return
        }
        blockingBusy.launchIn(scope) { runStartFromFile(bytes, filename, mode, listId, listName) }
    }

    suspend fun runStartFromFile(
        bytes: ByteArray,
        filename: String,
        mode: String,
        listId: String,
        listName: String,
    ) {
        runCatching { repository.createImportJobFile(bytes, filename, listId, mode) }
            .onSuccess { progress ->
                persistence.saveJobId(progress.job_id)
                _state.value = progress.toState(
                    ImportJobState(
                        targetListName = listName,
                        sourceName = filename,
                        mode = mode,
                        dailyUsed = progress.daily_used,
                        dailyLimit = progress.daily_limit,
                    ),
                )
                backgroundJobs.enqueueImport(replace = true)
                startPoll()
            }
            .onFailure { e ->
                if (e is HttpException && e.code() == 409) {
                    restoreActive()
                } else {
                    publishLocalError(
                        e.userMessage(strings.get(R.string.err_import_file), strings),
                    )
                }
            }
    }

    fun startFromPaste(
        text: String,
        mode: String,
        listId: String,
        listName: String,
    ) {
        if (_state.value.blocksUi) return
        if (!networkMonitor.isCurrentlyOnline()) {
            publishLocalError(strings.get(R.string.import_online_only))
            return
        }
        val trimmed = text.trim()
        if (trimmed.isBlank()) {
            publishLocalError(strings.get(R.string.err_import_empty))
            return
        }
        blockingBusy.launchIn(scope) { runStartFromPaste(trimmed, mode, listId, listName) }
    }

    suspend fun runStartFromPaste(
        text: String,
        mode: String,
        listId: String,
        listName: String,
    ) {
        runCatching { repository.createImportJob(text, listId, mode) }
            .onSuccess { progress ->
                persistence.saveJobId(progress.job_id)
                _state.value = progress.toState(
                    ImportJobState(
                        targetListName = listName,
                        sourceName = "paste",
                        mode = mode,
                        dailyUsed = progress.daily_used,
                        dailyLimit = progress.daily_limit,
                    ),
                )
                backgroundJobs.enqueueImport(replace = true)
                startPoll()
            }
            .onFailure { e ->
                if (e is HttpException && e.code() == 409) {
                    restoreActive()
                } else {
                    publishLocalError(e.userMessage(strings.get(R.string.err_import), strings))
                }
            }
    }

    fun requestCancel() {
        val cur = _state.value
        if (!cur.busy && cur.status != ImportStatus.Review) return
        _state.value = cur.copy(showAbortConfirm = true)
    }

    fun dismissAbortConfirm() {
        val cur = _state.value
        if (!cur.showAbortConfirm) return
        _state.value = cur.copy(showAbortConfirm = false)
    }

    fun confirmCancel() {
        val jobId = _state.value.jobId
        dismissResult()
        if (jobId.isNullOrBlank()) return
        scope.launch {
            runCatching { repository.cancelImportJob(jobId) }
        }
    }

    fun toggleReadyItem(itemId: String) {
        val cur = _state.value
        if (cur.status != ImportStatus.Review) return
        if (cur.readyItems.none { it.id == itemId }) return
        val next = if (itemId in cur.selectedItemIds) {
            cur.selectedItemIds - itemId
        } else {
            cur.selectedItemIds + itemId
        }
        _state.value = cur.copy(selectedItemIds = next)
    }

    fun confirmCommit() {
        val cur = _state.value
        if (cur.status != ImportStatus.Review) return
        val jobId = cur.jobId ?: return
        if (!cur.canConfirmSelected) return
        if (blockingBusy.busy.value) return
        val itemIds = cur.selectedItemIds.toList()
        blockingBusy.launchIn(scope) {
            runCatching { repository.commitImportJob(jobId, itemIds) }
                .onSuccess {
                    val next = it.toState(cur)
                    if (next.status == ImportStatus.Done) {
                        runCatching { repository.refreshLocalAfterImport(next.targetListId) }
                        watchImportedCards(next)
                    }
                    _state.value = next
                    if (next.busy) backgroundJobs.enqueueImport(replace = true)
                    startPoll()
                }
                .onFailure { e ->
                    publishLocalError(e.userMessage(strings.get(R.string.err_save_cards), strings))
                }
        }
    }

    fun dismissResult(openList: Boolean = false) {
        val listId = _state.value.targetListId
        val dailyUsed = _state.value.dailyUsed
        val dailyLimit = _state.value.dailyLimit
        scope.launch { persistence.saveJobId(null) }
        _state.value = ImportJobState(dailyUsed = dailyUsed, dailyLimit = dailyLimit)
        stopPoll()
        backgroundJobs.cancelImport()
        if (openList && !listId.isNullOrBlank()) {
            _navigateToList.tryEmit(listId)
        }
    }

    fun setUiError(message: String) {
        if (_state.value.busy) return
        publishLocalError(message)
    }

    fun expandSection(section: String?) {
        val cur = _state.value
        val next = if (cur.expandedSection == section) null else section
        _state.value = cur.copy(expandedSection = next)
        val jobId = cur.jobId
        if (next != null && cur.items.isEmpty() && !jobId.isNullOrBlank()) {
            scope.launch { refreshItems(jobId) }
        }
    }

    private suspend fun refreshItems(jobId: String) {
        runCatching { repository.getImportJob(jobId, includeItems = true) }
            .onSuccess { detail ->
                if (detail.items.isNotEmpty()) {
                    _state.value = detail.toState(_state.value, includeItems = true)
                }
            }
    }

    fun copiedErrorsNotice() {
        val n = _state.value.failedItems.size
        _state.value = _state.value.copy(
            notice = strings.get(R.string.import_errors_copied, n),
        )
    }

    fun onAppForeground() {
        scope.launch {
            if (!repository.hasSyncableSession()) return@launch
            if (_state.value.jobId.isNullOrBlank()) {
                val stored = persistence.loadJobId()
                if (stored.isNullOrBlank()) return@launch
                restore()
                return@launch
            }
            startPoll()
        }
    }

    /** WorkManager w tle — ten sam ingest co pętla poll, bez czekania na UI. */
    suspend fun ingestRemoteProgress(progress: ImportJobProgressResponse) {
        applyProgress(progress)
    }

    private suspend fun restore() {
        if (!repository.hasSyncableSession()) return
        val stored = persistence.loadJobId()
        if (!stored.isNullOrBlank()) {
            val detail = runCatching { repository.getImportJob(stored, includeItems = true) }.getOrNull()
            if (detail != null) {
                val restored = detail.toState()
                if (restored.status == ImportStatus.Cancelled) {
                    persistence.saveJobId(null)
                    return
                }
                if (restored.status == ImportStatus.Done || restored.status == ImportStatus.Failed) {
                    runCatching { repository.refreshLocalAfterImport(restored.targetListId) }
                    if (restored.status == ImportStatus.Done) watchImportedCards(restored)
                }
                _state.value = restored
                startPoll()
                return
            }
        }
        restoreActive()
    }

    private suspend fun restoreActive() {
        val active = runCatching { repository.getActiveImportJob() }.getOrNull() ?: return
        _state.value = _state.value.copy(
            dailyUsed = active.daily_used,
            dailyLimit = active.daily_limit,
        )
        val jobId = active.job_id
        if (jobId.isNullOrBlank() || active.status.equals("idle", ignoreCase = true)) {
            return
        }
        persistence.saveJobId(jobId)
        val detail = runCatching { repository.getImportJob(jobId, includeItems = true) }
            .getOrDefault(active)
        _state.value = detail.toState(_state.value)
        startPoll()
    }

    /** Odświeża licznik dnia bez aktywnego zadania (zakładka Import). */
    fun refreshDailyQuota() {
        scope.launch {
            val active = runCatching { repository.getActiveImportJob() }.getOrNull() ?: return@launch
            _state.value = _state.value.copy(
                dailyUsed = active.daily_used,
                dailyLimit = active.daily_limit,
            )
            if (!active.job_id.isNullOrBlank() &&
                !active.status.equals("idle", ignoreCase = true) &&
                !_state.value.blocksUi
            ) {
                restoreActive()
            }
        }
    }

    private fun startPoll() {
        pollJob?.cancel()
        pollJob = scope.launch {
            while (isActive) {
                val id = _state.value.jobId ?: break
                val working = _state.value.busy
                val progress = runCatching {
                    if (working) {
                        repository.getImportJobProgress(id)
                    } else if (_state.value.status == ImportStatus.Review && _state.value.items.isEmpty()) {
                        repository.getImportJob(id, includeItems = true)
                    } else {
                        null
                    }
                }.getOrNull()
                if (progress != null) {
                    applyProgress(progress)
                    if (_state.value.status == ImportStatus.Cancelled) {
                        dismissResult()
                        break
                    }
                }
                if (!_state.value.busy) {
                    if (_state.value.status == ImportStatus.Review && _state.value.items.isEmpty()) {
                        delay(1_000)
                        continue
                    }
                    break
                }
                delay(1_000)
            }
        }
    }

    private suspend fun applyProgress(progress: ImportJobProgressResponse) {
        val id = progress.job_id
        if (id.isNullOrBlank()) {
            _state.value = _state.value.copy(
                dailyUsed = progress.daily_used,
                dailyLimit = progress.daily_limit,
            )
            return
        }
        val include = progress.status == "review" ||
            progress.status == "done" ||
            progress.status == "failed" ||
            progress.status == "cancelled"
        val next = if (include && progress.items.isEmpty()) {
            runCatching { repository.getImportJob(id, includeItems = true) }.getOrNull()
                ?: progress
        } else {
            progress
        }
        val nextState = next.toState(_state.value, includeItems = true)
        val prevCreated = _state.value.createdCount
        val becameDone = nextState.status == ImportStatus.Done &&
            _state.value.status != ImportStatus.Done
        val becameFailed = nextState.status == ImportStatus.Failed &&
            _state.value.status != ImportStatus.Failed
        if (becameDone || becameFailed) {
            runCatching { repository.refreshLocalAfterImport(nextState.targetListId) }
            if (becameDone) watchImportedCards(nextState)
        } else if (
            nextState.createdCount > prevCreated &&
            (nextState.createdCount == 1 || nextState.createdCount % 10 == 0)
        ) {
            repository.requestBackgroundSync()
        }
        _state.value = nextState
    }

    private fun stopPoll() {
        pollJob?.cancel()
        pollJob = null
    }

    private fun publishLocalError(message: String) {
        _state.value = ImportJobState(status = ImportStatus.Error, error = message)
    }

    private suspend fun watchImportedCards(state: ImportJobState) {
        var ids = state.items.mapNotNull { it.created_card_id?.trim()?.takeIf(String::isNotEmpty) }
        if (ids.isEmpty()) {
            val jobId = state.jobId ?: return
            ids = runCatching { repository.getImportJob(jobId, includeItems = true) }
                .getOrNull()
                ?.items
                ?.mapNotNull { it.created_card_id?.trim()?.takeIf(String::isNotEmpty) }
                .orEmpty()
        }
        if (ids.isNotEmpty()) {
            repository.watchImportCards(ids)
            repository.evaluateReadyBatches()
        }
    }
}
