package com.vocabulario.app.ui.report

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.ContentReportDraft
import com.vocabulario.app.data.ContentReportRepository
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.ReportSubmitResult
import com.vocabulario.app.data.api.ReportLimits
import com.vocabulario.app.data.api.ReportReason
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

/** Co zgłaszamy; [excerpt] to dokładnie ten tekst, który użytkownik zobaczy w podglądzie. */
data class ReportTarget(
    val kind: String,
    val targetId: String?,
    val field: String,
    val excerpt: String,
)

sealed interface ReportPhase {
    object Editing : ReportPhase

    object Sending : ReportPhase

    data class Sent(val status: String) : ReportPhase

    data class Queued(val reportId: String) : ReportPhase

    object Rejected : ReportPhase
}

data class ReportUiState(
    val reason: String = ReportReason.INCORRECT,
    val note: String = "",
    val phase: ReportPhase = ReportPhase.Editing,
    val failed: Boolean = false,
)

@HiltViewModel
class ContentReportViewModel @Inject constructor(
    private val reports: ContentReportRepository,
    private val learning: LearningRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ReportUiState())
    val state: StateFlow<ReportUiState> = _state.asStateFlow()

    fun setReason(value: String) = _state.update { it.copy(reason = value) }

    fun setNote(value: String) = _state.update { it.copy(note = value.take(ReportLimits.NOTE_MAX)) }

    /** Jedno aktywne wysyłanie naraz; powtórne dotknięcie w trakcie jest ignorowane. */
    fun submit(target: ReportTarget) {
        val current = _state.value
        if (current.phase != ReportPhase.Editing) return
        _state.update { it.copy(phase = ReportPhase.Sending, failed = false) }
        viewModelScope.launch {
            val result = try {
                reports.submit(
                    ContentReportDraft(
                        profileId = learning.activeProfileId(),
                        targetKind = target.kind,
                        targetId = target.targetId,
                        field = target.field,
                        reason = current.reason,
                        excerpt = target.excerpt,
                        note = current.note,
                    ),
                )
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                null
            }
            _state.update { it.copy(phase = phaseFor(result), failed = result == null) }
        }
    }

    fun retry() {
        val queued = _state.value.phase as? ReportPhase.Queued ?: return
        _state.update { it.copy(phase = ReportPhase.Sending) }
        viewModelScope.launch {
            val result = try {
                reports.retry(queued.reportId)
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                ReportSubmitResult.Queued(queued.reportId)
            }
            _state.update { it.copy(phase = phaseFor(result)) }
        }
    }

    fun discardQueued() {
        val queued = _state.value.phase as? ReportPhase.Queued ?: return
        viewModelScope.launch {
            reports.cancel(queued.reportId)
            _state.update { it.copy(phase = ReportPhase.Editing) }
        }
    }

    private fun phaseFor(result: ReportSubmitResult?): ReportPhase = when (result) {
        is ReportSubmitResult.Sent -> ReportPhase.Sent(result.receipt.status)
        is ReportSubmitResult.Queued -> ReportPhase.Queued(result.reportId)
        is ReportSubmitResult.Rejected -> ReportPhase.Rejected
        null -> ReportPhase.Editing
    }
}
