package com.vocabulario.app.ui.sync

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.NetworkMonitor
import com.vocabulario.app.data.sync.BlockedAction
import com.vocabulario.app.data.sync.BlockedItem
import com.vocabulario.app.data.sync.QueueSnapshot
import com.vocabulario.app.data.sync.SyncHeadline
import com.vocabulario.app.data.sync.SyncResult
import com.vocabulario.app.data.sync.SyncStatus
import com.vocabulario.app.data.sync.blockedActions
import com.vocabulario.app.data.sync.syncHeadline
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

/** Wiersz zablokowanej pracy; [profileLabel] to para języków, nie tekst z backendu. */
data class BlockedRow(
    val item: BlockedItem,
    val profileLabel: String?,
    val actions: List<BlockedAction>,
)

enum class SyncNotice { NEEDS_NETWORK, CONTENT_UPDATED }

data class SyncStatusUi(
    val headline: SyncHeadline = SyncHeadline.IDLE,
    val queue: QueueSnapshot = QueueSnapshot(),
    val blocked: List<BlockedRow> = emptyList(),
    val lastCompleteAt: Long? = null,
    val notice: SyncNotice? = null,
)

@HiltViewModel
class SyncStatusViewModel @Inject constructor(
    private val repository: LearningRepository,
    networkMonitor: NetworkMonitor,
) : ViewModel() {

    private val notice = MutableStateFlow<SyncNotice?>(null)

    private data class Queue(val snapshot: QueueSnapshot, val blocked: List<BlockedRow>)

    private val queue = repository.observeQueue().map { snapshot ->
        val labels = repository.listProfiles()
            .associate { it.id to "${it.app_lang.uppercase()} → ${it.learning_lang.uppercase()}" }
        val rows = repository.blockedItems().map { item ->
            BlockedRow(item, item.profileId?.let(labels::get), blockedActions(item))
        }
        Queue(snapshot, rows)
    }

    val state: StateFlow<SyncStatusUi> = combine(
        networkMonitor.isOnline,
        repository.syncStatus,
        queue,
        notice,
    ) { online, status: SyncStatus, q, note ->
        val lastReport = when (val last = status.last) {
            is SyncResult.Complete -> last.report
            is SyncResult.Partial -> last.report
            is SyncResult.Offline -> last.report
            is SyncResult.AuthRequired -> last.report
            is SyncResult.VerificationRequired -> last.report
            is SyncResult.LegalAcceptanceRequired -> last.report
            is SyncResult.UpdateRequired -> last.report
            is SyncResult.Failed -> last.report
            else -> null
        }
        SyncStatusUi(
            headline = syncHeadline(online, status, q.snapshot),
            queue = q.snapshot,
            blocked = q.blocked,
            lastCompleteAt = status.lastCompleteAt,
            notice = note ?: if ((lastReport?.supersededReviews ?: 0) > 0) {
                SyncNotice.CONTENT_UPDATED
            } else {
                null
            },
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), SyncStatusUi())

    init {
        viewModelScope.launch { repository.loadLastCompleteSyncAt() }
    }

    fun retry() {
        notice.value = null
        repository.requestBackgroundSync()
    }

    fun act(row: BlockedRow, action: BlockedAction) {
        notice.value = null
        val item = row.item
        viewModelScope.launch {
            when (action) {
                BlockedAction.DISCARD -> repository.discardBlocked(item.kind, item.id)
                BlockedAction.ACCEPT_SERVER -> item.id.toLongOrNull()?.let { repository.acceptServerProfile(it) }
                BlockedAction.APPLY_MINE -> {
                    val reopened = item.id.toLongOrNull()?.let { repository.applyMyProfileChanges(it) } ?: false
                    if (!reopened) notice.value = SyncNotice.NEEDS_NETWORK
                }
            }
        }
    }
}
