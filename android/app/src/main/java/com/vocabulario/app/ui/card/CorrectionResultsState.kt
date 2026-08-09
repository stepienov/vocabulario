package com.vocabulario.app.ui.card

import com.vocabulario.app.data.api.CardCorrectionResponse

data class CorrectionResultItem(
    val correction: CardCorrectionResponse,
    val cardLemma: String,
)

data class CorrectionResultsState(
    val active: CorrectionResultItem? = null,
    val pending: List<CorrectionResultItem> = emptyList(),
) {
    fun enqueue(item: CorrectionResultItem, blockersActive: Boolean): CorrectionResultsState {
        if (active == null && !blockersActive) return copy(active = item)
        return copy(pending = pending + item)
    }

    /** Dismiss active result; show next queued item unless blockers are active. */
    fun dismiss(blockersActive: Boolean): CorrectionResultsState {
        if (blockersActive) return copy(active = null)
        val next = pending.firstOrNull() ?: return CorrectionResultsState()
        return copy(active = next, pending = pending.drop(1))
    }

    /** Hide active result when opening self-edit; next item waits until self-edit flow ends. */
    fun clearActiveForSelfEdit(): CorrectionResultsState = copy(active = null)

    fun tryShowNext(blockersActive: Boolean): CorrectionResultsState {
        if (active != null || blockersActive || pending.isEmpty()) return this
        return copy(active = pending.first(), pending = pending.drop(1))
    }
}

fun HomeUiStateSelfEditActive(
    selfEditCard: Any?,
    selfEditWarningOpen: Boolean,
    selfEditProgressCardId: String?,
    selfEditSaving: Boolean,
    selfEditValidating: Boolean,
): Boolean =
    selfEditCard != null ||
        selfEditWarningOpen ||
        !selfEditProgressCardId.isNullOrBlank() ||
        selfEditSaving ||
        selfEditValidating
