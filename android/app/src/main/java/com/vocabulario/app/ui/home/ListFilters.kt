package com.vocabulario.app.ui.home

import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.normalizePosKey

enum class ListSortOrder {
    LemmaAsc,
    LemmaDesc,
    PosAsc,
    Newest,
    Oldest,
    Status,
}

enum class CardStateFilter {
    New,
    Learning,
    Review,
    Mastered,
}

data class ListFilterState(
    val pos: Set<String> = emptySet(),
    val states: Set<CardStateFilter> = emptySet(),
) {
    val isActive: Boolean get() = pos.isNotEmpty() || states.isNotEmpty()
    val activeCount: Int get() = (if (pos.isNotEmpty()) 1 else 0) + (if (states.isNotEmpty()) 1 else 0)
}

fun cardStateFilterOf(card: CardResponse): CardStateFilter {
    val status = card.srs_status
    val interval = card.srs_interval_days ?: 0.0
    return when {
        status == "learning" || status == "relearning" -> CardStateFilter.Learning
        status == "review" && interval >= 21.0 -> CardStateFilter.Mastered
        status == "review" -> CardStateFilter.Review
        else -> CardStateFilter.New // null / new / unknown
    }
}

fun applyListFilterSort(
    words: List<CardResponse>,
    filter: ListFilterState,
    sort: ListSortOrder,
): List<CardResponse> {
    val filtered = words.filter { card ->
        val posOk = filter.pos.isEmpty() || normalizePosKey(card.pos) in filter.pos
        val stateOk = filter.states.isEmpty() || cardStateFilterOf(card) in filter.states
        posOk && stateOk
    }
    return when (sort) {
        ListSortOrder.LemmaAsc -> filtered.sortedBy { it.lemma_l2.lowercase() }
        ListSortOrder.LemmaDesc -> filtered.sortedByDescending { it.lemma_l2.lowercase() }
        ListSortOrder.PosAsc -> filtered.sortedWith(
            compareBy<CardResponse> {
                val key = normalizePosKey(it.pos)
                if (key == "unknown") "\uFFFF" else key
            }.thenBy { it.lemma_l2.lowercase() },
        )
        ListSortOrder.Newest -> filtered.sortedByDescending { it.created_at }
        ListSortOrder.Oldest -> filtered.sortedBy { it.created_at }
        ListSortOrder.Status -> filtered.sortedWith(
            compareBy<CardResponse> { cardStateFilterOf(it).ordinal }
                .thenBy { it.lemma_l2.lowercase() },
        )
    }
}

/** Canonical POS keys used by list filters (9 + unknown). */
val LIST_FILTER_POS_KEYS = listOf(
    "noun", "verb", "adj", "adv", "prep", "conj", "pron", "det", "interj", "unknown",
)
