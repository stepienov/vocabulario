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
    fun enqueue(item: CorrectionResultItem, blockersActive: Boolean = false): CorrectionResultsState {
        if (active == null && !blockersActive) return copy(active = item)
        return copy(pending = pending + item)
    }

    fun dismiss(blockersActive: Boolean = false): CorrectionResultsState {
        if (blockersActive) return copy(active = null)
        val next = pending.firstOrNull() ?: return CorrectionResultsState()
        return copy(active = next, pending = pending.drop(1))
    }

    fun tryShowNext(blockersActive: Boolean = false): CorrectionResultsState {
        if (active != null || blockersActive || pending.isEmpty()) return this
        return copy(active = pending.first(), pending = pending.drop(1))
    }
}
