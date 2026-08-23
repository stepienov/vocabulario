package com.vocabulario.app.data

import com.vocabulario.app.data.api.WordListResponse
import com.vocabulario.app.data.local.db.CachedCardEntity

data class RelatedMembership(
    val displayLemma: String,
    val listName: String,
    val isSystemList: Boolean,
    val cardId: String,
    val pos: String?,
    val lemmaKeys: Set<String>,
)

data class RelatedMembershipIndex(
    val hits: List<RelatedMembership> = emptyList(),
) {
    fun find(lemma: String?, pos: String?): RelatedMembership? {
        val keys = lemmaKeys(lemma)
        if (keys.isEmpty()) return null
        val want = normalizePosKey(pos)
        val matches = hits.filter { hit ->
            hit.lemmaKeys.any { it in keys } && posCompatible(want, normalizePosKey(hit.pos))
        }
        return matches.minWithOrNull(
            compareBy<RelatedMembership> { if (it.isSystemList) 0 else 1 }
                .thenBy { it.listName },
        )
    }

    companion object {
        val Empty = RelatedMembershipIndex()
    }
}

fun posCompatible(left: String, right: String): Boolean {
    if (left == "unknown" || right == "unknown") return true
    return left == right
}

fun buildRelatedMembershipIndex(
    cards: List<CachedCardEntity>,
    lists: List<WordListResponse>,
): RelatedMembershipIndex {
    val listById = lists.associateBy { it.id }
    val system = lists.firstOrNull { it.is_system }
    val hits = ArrayList<RelatedMembership>(cards.size)
    for (card in cards) {
        val list = when {
            card.deckId.isNullOrBlank() -> system
            else -> listById[card.deckId]
        } ?: continue
        val keys = lemmaKeys(card.lemmaL2)
        if (keys.isEmpty()) continue
        hits.add(
            RelatedMembership(
                displayLemma = card.lemmaL2,
                listName = list.name,
                isSystemList = list.is_system,
                cardId = card.id,
                pos = card.pos,
                lemmaKeys = keys,
            ),
        )
    }
    return RelatedMembershipIndex(hits)
}

private const val AR_DEFINITE = "ال"

fun formatLemmaWithArticle(lemma: String, article: String?): String {
    val stem = lemma.trim()
    val art = article?.trim().orEmpty()
    if (stem.isEmpty()) return art
    if (art.isEmpty()) return stem
    val stemLower = stem.lowercase()
    val artLower = art.lowercase()
    if (stemLower == artLower) return stem
    if (stemLower.startsWith(artLower) &&
        art.length < stem.length &&
        !stem[art.length].isLetter()
    ) {
        return stem
    }
    if (art == AR_DEFINITE && stem.startsWith(AR_DEFINITE)) return stem
    if (art.endsWith("'") || art.endsWith("’") || art == AR_DEFINITE) {
        return art + stem
    }
    return "$art $stem"
}
