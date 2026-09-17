package com.vocabulario.app.ui.practice

import com.vocabulario.app.data.api.CardResponse
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ListFlashcardQueueTest {

    private fun card(id: String, status: String = "ready") = CardResponse(
        id = id,
        lemma_l2 = id,
        content = buildJsonObject { },
        created_at = "",
        enrichment_status = status,
    )

    @Test
    fun eligibleKeepsStudyableOnly() {
        val cards = listOf(
            card("a", "ready"),
            card("b", "learnable"),
            card("c", "pending"),
            card("d", "awaiting_network"),
        )
        val eligible = eligibleListFlashcards(cards).map { it.id }
        assertEquals(listOf("a", "b"), eligible)
    }

    @Test
    fun nextAfterRevealCountsReviewedAndAdvances() {
        val queue = ListFlashcardQueue(listOf(card("casa"), card("mesa")))
        queue.reveal()
        assertFalse(queue.next())
        assertEquals("mesa", queue.current?.id)
        assertEquals(1, queue.reviewed)
        assertEquals(0, queue.added)
        assertFalse(queue.revealed)
    }

    @Test
    fun nextOnLastCardFinishes() {
        val queue = ListFlashcardQueue(listOf(card("casa")))
        queue.reveal()
        assertTrue(queue.next())
        assertTrue(queue.isFinished)
        assertEquals(1, queue.snapshot().reviewed)
    }

    @Test
    fun commitAddRemovesCurrentAndKeepsFollowing() {
        val queue = ListFlashcardQueue(listOf(card("casa"), card("mesa")))
        queue.reveal()
        assertFalse(queue.commitAdd())
        assertEquals("mesa", queue.current?.id)
        assertEquals(1, queue.added)
        assertEquals(1, queue.reviewed)
    }

    @Test
    fun commitAddOnLastFinishes() {
        val queue = ListFlashcardQueue(listOf(card("casa")))
        queue.reveal()
        assertTrue(queue.commitAdd())
        assertEquals(1, queue.added)
        assertEquals(1, queue.reviewed)
    }

    @Test
    fun exitWithoutRevealDoesNotCountCurrent() {
        val queue = ListFlashcardQueue(listOf(card("casa"), card("mesa")))
        assertEquals(0, queue.snapshotIncludingCurrent().reviewed)
    }

    @Test
    fun exitAfterRevealCountsCurrent() {
        val queue = ListFlashcardQueue(listOf(card("casa"), card("mesa")))
        queue.reveal()
        val summary = queue.snapshotIncludingCurrent()
        assertEquals(1, summary.reviewed)
        assertEquals(0, summary.added)
    }
}
