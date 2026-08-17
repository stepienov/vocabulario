package com.vocabulario.app.data.imports

import com.vocabulario.app.R
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.NetworkMonitor
import com.vocabulario.app.data.api.userMessage
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
        scope.launch {
            runCatching { repository.createImportJobFile(bytes, filename, listId, mode) }
                .onSuccess { progress ->
                    persistence.saveJobId(progress.job_id)
                    _state.value = progress.toState(
                        ImportJobState(targetListName = listName, sourceName = filename, mode = mode),
                    )
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
        scope.launch {
            runCatching { repository.createImportJob(trimmed, listId, mode) }
                .onSuccess { progress ->
                    persistence.saveJobId(progress.job_id)
                    _state.value = progress.toState(
                        ImportJobState(
                            targetListName = listName,
                            sourceName = "paste",
                            mode = mode,
                        ),
                    )
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

    fun confirmCommit() {
        val cur = _state.value
        if (cur.status != ImportStatus.Review) return
        val jobId = cur.jobId ?: return
        if (cur.readyCount <= 0) return
        scope.launch {
            runCatching { repository.commitImportJob(jobId) }
                .onSuccess {
                    val next = it.toState(cur)
                    if (next.status == ImportStatus.Done) {
                        runCatching { repository.refreshLocalAfterImport(next.targetListId) }
                        watchImportedCards(next)
                    }
                    _state.value = next
                    startPoll()
                }
                .onFailure { e ->
                    publishLocalError(e.userMessage(strings.get(R.string.err_save_cards), strings))
                }
        }
    }

    fun dismissResult(openList: Boolean = false) {
        val listId = _state.value.targetListId
        scope.launch { persistence.saveJobId(null) }
        _state.value = ImportJobState()
        stopPoll()
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
        startPoll()
    }

    private suspend fun restore() {
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
        val active = runCatching { repository.getActiveImportJob() }.getOrNull()
        if (active != null) {
            persistence.saveJobId(active.job_id)
            val detail = runCatching { repository.getImportJob(active.job_id, includeItems = true) }
                .getOrDefault(active)
            _state.value = detail.toState()
            startPoll()
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
