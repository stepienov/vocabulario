package com.vocabulario.app.data.imports

import com.vocabulario.app.R
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.NetworkMonitor
import com.vocabulario.app.data.api.ImportDisplayCard
import com.vocabulario.app.data.api.ImportValidWord
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.i18n.UiStrings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
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
    private val persistMutex = Mutex()

    private val _state = MutableStateFlow(ImportJobState())
    val state: StateFlow<ImportJobState> = _state.asStateFlow()

    private val _navigateToList = MutableSharedFlow<String>(extraBufferCapacity = 1)
    val navigateToList: SharedFlow<String> = _navigateToList.asSharedFlow()

    private var workJob: Job? = null
    private var cancelCommitRequested = false

    init {
        scope.launch {
            val restored = persistence.load() ?: return@launch
            when (restored.status) {
                ImportStatus.Idle, ImportStatus.Done, ImportStatus.Error -> {
                    _state.value = restored
                }
                ImportStatus.Review -> {
                    _state.value = restored
                }
                ImportStatus.Processing -> {
                    publish(
                        ImportJobState(
                            status = ImportStatus.Error,
                            sourceName = restored.sourceName,
                            mode = restored.mode,
                            targetListId = restored.targetListId,
                            targetListName = restored.targetListName,
                            error = strings.get(R.string.import_interrupted),
                        ),
                    )
                }
                ImportStatus.Committing -> {
                    _state.value = restored.copy(
                        status = ImportStatus.Committing,
                        processed = 0,
                        showAbortConfirm = false,
                    )
                    resumeCommit()
                }
            }
        }
    }

    fun startFromFile(
        bytes: ByteArray,
        filename: String,
        mode: String,
        listId: String,
        listName: String,
    ) {
        if (_state.value.busy) return
        if (!networkMonitor.isCurrentlyOnline()) {
            publish(
                ImportJobState(
                    status = ImportStatus.Error,
                    error = strings.get(R.string.import_online_only),
                ),
            )
            return
        }
        if (bytes.isEmpty()) {
            publish(
                ImportJobState(
                    status = ImportStatus.Error,
                    error = strings.get(R.string.err_import_empty_file),
                ),
            )
            return
        }
        beginProcessing(
            sourceName = filename,
            mode = mode,
            listId = listId,
            listName = listName,
        ) {
            if (mode == "preserve") {
                repository.ingestImportFilePreserve(bytes, filename)
                    .also { applyAnalyzed(displayCards = it.cards) }
            } else {
                repository.ingestImportFile(bytes, filename, mode = "vocabulario")
                    .also { applyAnalyzed(valid = it.valid, invalid = it.invalid) }
            }
        }
    }

    fun startFromPaste(
        text: String,
        mode: String,
        listId: String,
        listName: String,
    ) {
        if (_state.value.busy) return
        if (!networkMonitor.isCurrentlyOnline()) {
            publish(
                ImportJobState(
                    status = ImportStatus.Error,
                    error = strings.get(R.string.import_online_only),
                ),
            )
            return
        }
        val trimmed = text.trim()
        if (trimmed.isBlank()) {
            publish(
                ImportJobState(
                    status = ImportStatus.Error,
                    error = strings.get(R.string.err_import_empty),
                ),
            )
            return
        }
        beginProcessing(
            sourceName = strings.get(R.string.import_paste_source),
            mode = mode,
            listId = listId,
            listName = listName,
        ) {
            if (mode == "preserve") {
                repository.ingestImportPreserve(trimmed)
                    .also { applyAnalyzed(displayCards = it.cards) }
            } else {
                repository.ingestImport(trimmed, mode = "vocabulario")
                    .also { applyAnalyzed(valid = it.valid, invalid = it.invalid) }
            }
        }
    }

    fun toggleItem(key: String) {
        val cur = _state.value
        if (cur.status != ImportStatus.Review) return
        val next = if (key in cur.deselectedKeys) {
            cur.deselectedKeys - key
        } else {
            cur.deselectedKeys + key
        }
        publish(cur.copy(deselectedKeys = next))
    }

    fun requestCancel() {
        val cur = _state.value
        if (!cur.busy) return
        publish(cur.copy(showAbortConfirm = true))
    }

    fun dismissAbortConfirm() {
        val cur = _state.value
        if (!cur.showAbortConfirm) return
        publish(cur.copy(showAbortConfirm = false))
    }

    fun confirmCancel() {
        val cur = _state.value
        when (cur.status) {
            ImportStatus.Processing -> {
                workJob?.cancel()
                workJob = null
                publish(ImportJobState())
            }
            ImportStatus.Committing -> {
                cancelCommitRequested = true
                publish(cur.copy(showAbortConfirm = false))
            }
            ImportStatus.Review -> {
                publish(ImportJobState())
            }
            else -> publish(cur.copy(showAbortConfirm = false))
        }
    }

    fun confirmCommit() {
        val cur = _state.value
        if (cur.status != ImportStatus.Review) return
        val total = cur.selectedCount
        if (total <= 0 || cur.targetListId.isNullOrBlank()) return
        cancelCommitRequested = false
        publish(
            cur.copy(
                status = ImportStatus.Committing,
                processed = 0,
                total = total,
                showAbortConfirm = false,
            ),
        )
        resumeCommit()
    }

    fun dismissResult(openList: Boolean = false) {
        val listId = _state.value.targetListId
        publish(ImportJobState())
        if (openList && !listId.isNullOrBlank()) {
            _navigateToList.tryEmit(listId)
        }
    }

    fun setUiError(message: String) {
        if (_state.value.busy) return
        publish(
            ImportJobState(
                status = ImportStatus.Error,
                error = message,
            ),
        )
    }

    private fun beginProcessing(
        sourceName: String,
        mode: String,
        listId: String,
        listName: String,
        block: suspend () -> Unit,
    ) {
        workJob?.cancel()
        cancelCommitRequested = false
        publish(
            ImportJobState(
                status = ImportStatus.Processing,
                sourceName = sourceName,
                mode = mode,
                targetListId = listId,
                targetListName = listName,
            ),
        )
        workJob = scope.launch {
            runCatching { block() }
                .onFailure { e ->
                    if (e is kotlinx.coroutines.CancellationException) {
                        publish(ImportJobState())
                        return@launch
                    }
                    val msg = e.userMessage(
                        if (sourceName == strings.get(R.string.import_paste_source)) {
                            strings.get(R.string.err_import)
                        } else {
                            strings.get(R.string.err_import_file)
                        },
                        strings,
                    )
                    publish(
                        ImportJobState(
                            status = ImportStatus.Error,
                            sourceName = sourceName,
                            mode = mode,
                            targetListId = listId,
                            targetListName = listName,
                            error = msg,
                        ),
                    )
                }
        }
    }

    private fun applyAnalyzed(
        valid: List<ImportValidWord> = emptyList(),
        invalid: List<String> = emptyList(),
        displayCards: List<ImportDisplayCard> = emptyList(),
    ) {
        val cur = _state.value
        if (cur.status != ImportStatus.Processing) return
        val itemCount = if (cur.mode == "preserve") {
            displayCards.size
        } else {
            valid.size + invalid.size
        }
        if (itemCount == 0) {
            publish(
                cur.copy(
                    status = ImportStatus.Error,
                    error = if (cur.mode == "preserve") {
                        strings.get(R.string.import_no_cards)
                    } else {
                        strings.get(R.string.import_no_valid)
                    },
                    valid = emptyList(),
                    displayCards = emptyList(),
                    invalid = emptyList(),
                ),
            )
            return
        }
        publish(
            cur.copy(
                status = ImportStatus.Review,
                valid = valid,
                displayCards = displayCards,
                invalid = invalid,
                deselectedKeys = emptySet(),
                total = if (cur.mode == "preserve") displayCards.size else valid.size,
                processed = 0,
            ),
        )
    }

    private fun resumeCommit() {
        workJob?.cancel()
        cancelCommitRequested = false
        workJob = scope.launch {
            val snapshot = _state.value
            val listId = snapshot.targetListId ?: run {
                publish(
                    snapshot.copy(
                        status = ImportStatus.Error,
                        error = strings.get(R.string.err_save_cards),
                    ),
                )
                return@launch
            }
            if (snapshot.mode == "preserve") {
                commitPreserve(listId, snapshot.selectedDisplayCards)
            } else {
                commitVocabulario(listId, snapshot.selectedValid)
            }
        }
    }

    private suspend fun commitVocabulario(listId: String, words: List<ImportValidWord>) {
        var created = 0
        var duplicates = 0
        var failed = 0
        val total = words.size.coerceAtLeast(1)
        words.forEachIndexed { index, w ->
            if (cancelCommitRequested) {
                finishCommit(
                    ImportResult(created = created, duplicates = duplicates, failed = failed),
                    listId,
                )
                return
            }
            runCatching {
                // Identycznie jak lookup → „+”: zawsze pełna karta lemma (enrich_card),
                // nigdy adaptive/phrase — to jest tryb Vocabulario.
                repository.addWordToList(
                    listId,
                    w.lemma,
                    w.pos,
                    w.gloss.ifBlank { null },
                    w.lexical_entry_id,
                    entryKind = "lemma",
                )
            }.onSuccess {
                created++
            }.onFailure { e ->
                if (e is HttpException && e.code() == 409) {
                    duplicates++
                } else {
                    failed++
                }
            }
            publish(
                _state.value.copy(
                    status = ImportStatus.Committing,
                    processed = index + 1,
                    total = words.size,
                ),
            )
        }
        finishCommit(ImportResult(created, duplicates, failed), listId)
    }

    private suspend fun commitPreserve(listId: String, cards: List<ImportDisplayCard>) {
        if (cards.isEmpty()) {
            finishCommit(ImportResult(), listId)
            return
        }
        publish(_state.value.copy(processed = 0, total = cards.size))
        runCatching { repository.commitImportDisplay(listId, cards) }
            .onSuccess { res ->
                publish(_state.value.copy(processed = cards.size, total = cards.size))
                finishCommit(
                    ImportResult(
                        created = res.created,
                        duplicates = res.skipped,
                        failed = 0,
                    ),
                    listId,
                )
            }
            .onFailure { e ->
                publish(
                    _state.value.copy(
                        status = ImportStatus.Error,
                        error = e.userMessage(strings, R.string.err_save_cards),
                        result = null,
                    ),
                )
            }
    }

    private suspend fun finishCommit(result: ImportResult, listId: String) {
        val cur = _state.value
        publish(
            cur.copy(
                status = ImportStatus.Done,
                processed = cur.total,
                result = result,
                showAbortConfirm = false,
                error = null,
                targetListId = listId,
            ),
        )
    }

    private fun publish(next: ImportJobState) {
        _state.value = next
        scope.launch {
            persistMutex.withLock {
                persistence.save(next)
            }
        }
    }
}
