package com.vocabulario.app.ui.home

import com.vocabulario.app.data.EnrichmentStatus
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.LookupCandidate
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class OptimisticListTileTest {

    @Test
    fun placeholder_usesPendingIdAndEnrichmentStatus() {
        val card = placeholderCardFromCandidate(
            LookupCandidate(
                lemma = "interrumpir",
                pos = "verb",
                gloss = "przerywać",
                enrichment_status = EnrichmentStatus.PENDING,
            ),
        )
        assertEquals(pendingCardId("interrumpir", "verb"), card.id)
        assertEquals(EnrichmentStatus.PENDING, card.enrichment_status)
        assertEquals("interrumpir", card.lemma_l2)
        assertTrue(card.isOptimisticCreatingTile())
    }

    @Test
    fun upsert_putsNewTileFirst() {
        val existing = listOf(ready("casa"))
        val creating = placeholderCardFromCandidate(
            LookupCandidate(lemma = "mesa", pos = "noun", gloss = "stół", enrichment_status = "pending"),
        )
        val merged = upsertListWord(existing, creating)
        assertEquals(listOf("mesa", "casa"), merged.map { it.lemma_l2 })
    }

    @Test
    fun merge_keepsCreatingTileWhenStaleCacheMissesIt() {
        val stale = listOf(ready("casa"))
        val creating = placeholderCardFromCandidate(
            LookupCandidate(
                lemma = "interrumpir",
                pos = "verb",
                gloss = "przerywać",
                list_name = "Uczę się",
                enrichment_status = EnrichmentStatus.PENDING,
            ),
        )
        val merged = mergeInFlightListWords(stale, listOf(creating))
        assertEquals(listOf("interrumpir", "casa"), merged.map { it.lemma_l2 })
        assertEquals(EnrichmentStatus.PENDING, merged.first().enrichment_status)
    }

    @Test
    fun merge_dropsPlaceholderOnceServerCardArrives() {
        val placeholder = placeholderCardFromCandidate(
            LookupCandidate(lemma = "mesa", pos = "noun", gloss = "stół", enrichment_status = "pending"),
        )
        val server = ready("mesa").copy(pos = "noun", enrichment_status = EnrichmentStatus.PENDING)
        val merged = mergeInFlightListWords(listOf(server), listOf(placeholder))
        assertEquals(listOf("mesa"), merged.map { it.lemma_l2 })
        assertEquals(server.id, merged.single().id)
    }

    @Test
    fun merge_doesNotDuplicateWhenCandidateAlreadyOnList() {
        val visible = listOf(ready("casa"), placeholderCardFromCandidate(
            LookupCandidate(lemma = "mesa", pos = "noun", gloss = "stół", enrichment_status = "pending"),
        ))
        val fromCandidate = placeholderCardFromCandidate(
            LookupCandidate(lemma = "mesa", pos = "noun", gloss = "stół", enrichment_status = "pending"),
        )
        val merged = mergeInFlightListWords(visible, listOf(fromCandidate))
        assertEquals(listOf("casa", "mesa"), merged.map { it.lemma_l2 })
    }

    @Test
    fun merge_dedupesPendingIdAndRealUuid() {
        val pending = placeholderCardFromCandidate(
            LookupCandidate(lemma = "mesa", pos = "noun", gloss = "stół", enrichment_status = "pending"),
        )
        val uuid = pending.copy(id = "srv-mesa")
        val merged = mergeInFlightListWords(emptyList(), listOf(pending, uuid))
        assertEquals(listOf("srv-mesa"), merged.map { it.id })
    }

    @Test
    fun switchingLists_doesNotCarryCreatingOrReadyCards() {
        val creating = ready("inestable").copy(enrichment_status = EnrichmentStatus.PREPARING)
        val state = HomeUiState(selectedListId = "old", listWords = listOf(creating, ready("casa")))

        val switched = selectListState(state, "new")
        val incoming = listOf(ready("mesa"))
        val displayed = mergeInFlightListWords(incoming, switched.listWords)

        assertEquals(listOf("mesa"), displayed.map { it.lemma_l2 })
        assertTrue(switched.listWords.isEmpty())
        assertTrue(mergeInFlightListWords(switched.listWords, emptyList()).isEmpty())
    }

    @Test
    fun reselectingSameList_keepsCreatingCards() {
        val creating = ready("inestable").copy(enrichment_status = EnrichmentStatus.PREPARING)
        val state = HomeUiState(selectedListId = "same", listWords = listOf(creating))

        val selected = selectListState(state, "same")

        assertEquals(listOf(creating), selected.listWords)
    }

    @Test
    fun lateListResult_isRejectedEvenAfterSwitchingBack() {
        val state = HomeUiState(selectedListId = "old")

        assertFalse(isCurrentListLoad(state, "new", 1, 2))
        assertFalse(isCurrentListLoad(state, "old", 0, 2))
        assertTrue(isCurrentListLoad(state, "old", 2, 2))
    }

    private fun ready(lemma: String) = CardResponse(
        id = "srv-$lemma",
        lemma_l2 = lemma,
        pos = "noun",
        content = buildJsonObject { },
        created_at = "",
        enrichment_status = EnrichmentStatus.READY,
        srs_status = "new",
    )
}
