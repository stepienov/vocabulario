package com.vocabulario.app.ui.practice

import com.vocabulario.app.data.EnrichmentStatus
import com.vocabulario.app.data.api.CardResponse

data class ListFlashcardSummary(
    val reviewed: Int,
    val added: Int,
)

internal fun CardResponse.isListFlashcardEligible(): Boolean =
    EnrichmentStatus.isStudyable(enrichment_status)

internal fun eligibleListFlashcards(cards: List<CardResponse>): List<CardResponse> =
    cards.filter { it.isListFlashcardEligible() }

/**
 * Kolejka fiszek z listy: bez SRS. Next zostawia kartę, add usuwa bieżącą.
 */
internal class ListFlashcardQueue(cards: List<CardResponse>) {
    private val remaining = cards.toMutableList()
    val initialSize: Int = cards.size
    var index: Int = 0
        private set
    var reviewed: Int = 0
        private set
    var added: Int = 0
        private set
    var revealed: Boolean = false
        private set

    val current: CardResponse? get() = remaining.getOrNull(index)
    val isFinished: Boolean get() = remaining.isEmpty() || index >= remaining.size

    val progress: Float
        get() {
            if (initialSize <= 0) return 0f
            val showing = if (isFinished) 0 else 1
            return ((reviewed + showing).coerceAtMost(initialSize)).toFloat() / initialSize
        }

    fun reveal() {
        if (current != null) revealed = true
    }

    /** @return true gdy sesja się skończyła */
    fun next(): Boolean {
        acknowledgeCurrentIfRevealed()
        if (index < remaining.size) index++
        revealed = false
        return isFinished
    }

    /** Zdejmuje bieżącą kartę (po udanym move). @return true gdy sesja się skończyła */
    fun commitAdd(): Boolean {
        if (current == null) return isFinished
        acknowledgeCurrentIfRevealed()
        added++
        remaining.removeAt(index)
        revealed = false
        return isFinished
    }

    fun snapshotIncludingCurrent(): ListFlashcardSummary {
        val extra = if (revealed && current != null) 1 else 0
        return ListFlashcardSummary(reviewed = reviewed + extra, added = added)
    }

    fun snapshot(): ListFlashcardSummary = ListFlashcardSummary(reviewed, added)

    private fun acknowledgeCurrentIfRevealed() {
        if (revealed && current != null) reviewed++
    }
}
