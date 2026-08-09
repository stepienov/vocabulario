package com.vocabulario.app.data.local

import com.vocabulario.app.data.api.CardResponse
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Test

class PendingInboxDisplayTest {

    private fun stub(lemma: String) = CardResponse(
        id = "pending-lookup-$lemma",
        lemma_l2 = lemma,
        content = buildJsonObject { },
        created_at = "",
        enrichment_status = "awaiting_network",
    )

    private fun card(
        id: String,
        lemma: String,
        gloss: String? = null,
        status: String = "ready",
    ) = CardResponse(
        id = id,
        lemma_l2 = lemma,
        gloss_primary = gloss,
        content = buildJsonObject { },
        created_at = "",
        enrichment_status = status,
    )

    @Test
    fun stubAndCardSameLemma_collapseToOneTile() {
        val result = PendingInboxDisplay.merge(
            stubs = listOf(stub("firanka")),
            cards = listOf(card("srv-1", "firanka")),
        )
        assertEquals(1, result.size)
        assertEquals("srv-1", result[0].id)
    }

    @Test
    fun stubMatchesCardByGloss_whenLemmaNormalized() {
        // Offline user wpisał „zloto"; serwer znormalizował do „el oro" z glosem „zloto".
        val result = PendingInboxDisplay.merge(
            stubs = listOf(stub("zloto")),
            cards = listOf(card("srv-2", "el oro", gloss = "zloto")),
        )
        assertEquals(1, result.size)
        assertEquals("el oro", result[0].lemma_l2)
    }

    @Test
    fun orphanStubWithoutCard_staysVisible() {
        val result = PendingInboxDisplay.merge(
            stubs = listOf(stub("kredens")),
            cards = emptyList(),
        )
        assertEquals(1, result.size)
        assertEquals("awaiting_network", result[0].enrichment_status)
    }

    @Test
    fun duplicateCardIds_areDeduped() {
        val result = PendingInboxDisplay.merge(
            stubs = emptyList(),
            cards = listOf(card("srv-3", "gato"), card("srv-3", "gato")),
        )
        assertEquals(1, result.size)
    }

    @Test
    fun awaitingAndPendingSortBeforeReady() {
        val result = PendingInboxDisplay.merge(
            stubs = listOf(stub("zebra")),
            cards = listOf(
                card("srv-ready", "apple", status = "ready"),
                card("srv-pending", "banana", status = "pending"),
            ),
        )
        // awaiting_network (zebra) → pending (banana) → ready (apple)
        assertEquals(listOf("zebra", "banana", "apple"), result.map { it.lemma_l2 })
    }

    private fun reviewStub(lemma: String) = CardResponse(
        id = "pending-lookup-$lemma",
        lemma_l2 = lemma,
        content = buildJsonObject { },
        created_at = "",
        enrichment_status = "needs_review",
    )

    @Test
    fun needsReviewStub_staysVisibleAndSortsFirst() {
        val result = PendingInboxDisplay.merge(
            stubs = listOf(reviewStub("trejtkoajtt")),
            cards = listOf(card("srv-ready", "apple", status = "ready")),
        )
        assertEquals(2, result.size)
        assertEquals("needs_review", result[0].enrichment_status)
        assertEquals("trejtkoajtt", result[0].lemma_l2)
    }

    @Test
    fun twoStubsDifferentWords_produceTwoTiles() {
        val result = PendingInboxDisplay.merge(
            stubs = listOf(stub("firanka"), stub("zloto")),
            cards = emptyList(),
        )
        assertEquals(2, result.size)
    }
}
