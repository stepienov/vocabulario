package com.vocabulario.app.ui.home

import com.vocabulario.app.data.api.CardResponse
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Test

class ListFiltersTest {

    private fun card(lemma: String, status: String? = "new", pos: String? = null) = CardResponse(
        id = lemma,
        lemma_l2 = lemma,
        pos = pos,
        content = buildJsonObject { },
        created_at = "",
        srs_status = status,
    )

    @Test
    fun sortLemmaAsc_ordersAlphabetically() {
        val sorted = applyListFilterSort(
            listOf(card("zebra"), card("apple")),
            ListFilterState(),
            ListSortOrder.LemmaAsc,
        )
        assertEquals("apple", sorted[0].lemma_l2)
    }

    @Test
    fun sortLemmaAsc_ignoresSpanishArticleOnNouns() {
        val sorted = applyListFilterSort(
            listOf(
                card("el amigo", pos = "noun"),
                card("la casa", pos = "noun"),
                card("beber", pos = "verb"),
            ),
            ListFilterState(),
            ListSortOrder.LemmaAsc,
        )
        assertEquals(listOf("el amigo", "beber", "la casa"), sorted.map { it.lemma_l2 })
    }

    @Test
    fun sortLemmaDesc_ignoresSpanishArticleOnNouns() {
        val sorted = applyListFilterSort(
            listOf(
                card("el libro", pos = "noun"),
                card("la mesa", pos = "noun"),
            ),
            ListFilterState(),
            ListSortOrder.LemmaDesc,
        )
        assertEquals(listOf("la mesa", "el libro"), sorted.map { it.lemma_l2 })
    }

    @Test
    fun filterNew_hidesReviewCards() {
        val filtered = applyListFilterSort(
            listOf(card("a", "new"), card("b", "review")),
            ListFilterState(states = setOf(CardStateFilter.New)),
            ListSortOrder.LemmaAsc,
        )
        assertEquals(1, filtered.size)
        assertEquals("a", filtered[0].lemma_l2)
    }
}
