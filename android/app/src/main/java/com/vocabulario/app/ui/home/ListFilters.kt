package com.vocabulario.app.ui.home

import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.normalizePosKey

enum class ListSortOrder {
    LemmaAsc,
    LemmaDesc,
    Newest,
    Oldest,
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
    query: String = "",
): List<CardResponse> {
    val filtered = words.filter { card ->
        val posOk = filter.pos.isEmpty() || normalizePosKey(card.pos) in filter.pos
        val stateOk = filter.states.isEmpty() || cardStateFilterOf(card) in filter.states
        posOk && stateOk && lemmaMatchesQuery(card.lemma_l2, query)
    }
    return when (sort) {
        ListSortOrder.LemmaAsc -> filtered.sortedBy { lemmaSortKey(it) }
        ListSortOrder.LemmaDesc -> filtered.sortedByDescending { lemmaSortKey(it) }
        ListSortOrder.Newest -> filtered.sortedByDescending { it.created_at }
        ListSortOrder.Oldest -> filtered.sortedBy { it.created_at }
    }
}

fun lemmaMatchesQuery(lemma: String, query: String): Boolean {
    val needle = query.trim()
    if (needle.isEmpty()) return true
    return lemma.contains(needle, ignoreCase = true)
}

/**
 * Alphabetical key: nouns with a leading article (el/la, le/la, der/die/das, …)
 * sort by the headword, not the article.
 */
internal fun lemmaSortKey(card: CardResponse): String {
    val raw = card.lemma_l2.trim().lowercase()
    val pos = normalizePosKey(card.pos)
    if (pos != "noun" && pos != "unknown") return raw
    val words = raw.split(Regex("\\s+")).filter { it.isNotEmpty() }
    if (words.size >= 2 && words[0].trimEnd('\'') in NOUN_SORT_ARTICLES) {
        return words.drop(1).joinToString(" ")
    }
    NOUN_SORT_ARTICLES.forEach { art ->
        val prefix = "$art'"
        if (raw.startsWith(prefix) && raw.length > prefix.length) {
            return raw.substring(prefix.length)
        }
    }
    return raw
}

/** Definite (and common indefinite) articles used in L2 noun lemmas. */
private val NOUN_SORT_ARTICLES = setOf(
    "el", "la", "los", "las",
    "le", "les", "un", "une",
    "der", "die", "das", "ein", "eine",
    "il", "lo", "i", "gli", "l",
    "o", "os", "as",
    "the", "a", "an",
    "het", "de",
)

/** Canonical POS keys used by list filters (9 + unknown). */
val LIST_FILTER_POS_KEYS = listOf(
    "noun", "verb", "adj", "adv", "prep", "conj", "pron", "det", "interj", "unknown",
)
