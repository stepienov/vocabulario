package com.vocabulario.app.data.local

import com.vocabulario.app.data.local.db.CachedCardEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LocalDashboardTest {

    private val now = 1_700_000_000_000L
    private val today = LocalDashboard.startOfDayMs(now)

    @Test
    fun dueAndNewMatchQueueRules() {
        val cards = listOf(
            card("due", status = "review", nextReviewAt = now - 1_000),
            card("later", status = "review", nextReviewAt = now + 86_400_000),
            card("new1", status = "new"),
            card("new2", status = "new"),
            card("pending", status = "new", enrichment = "pending"),
        )
        val stats = LocalDashboard.build(cards, newLimit = 20, nowMs = now)
        assertEquals(1, stats.due_count)
        assertEquals(2, stats.srs_new)
        assertEquals(2, stats.new_reserve)
        assertEquals(5, stats.cards_total)
        assertEquals(20, stats.new_limit)
    }

    @Test
    fun masteredUsesTwentyOneDayInterval() {
        val cards = listOf(
            card("m", status = "review", intervalDays = 21.0),
            card("r", status = "review", intervalDays = 5.0),
            card("l", status = "learning", intervalDays = 0.0),
        )
        val stats = LocalDashboard.build(cards, newLimit = 10, nowMs = now)
        assertEquals(1, stats.srs_mastered)
        assertEquals(2, stats.srs_learning)
    }

    @Test
    fun reviewsTodayFromLastReviewedAt() {
        val cards = listOf(
            card("a", status = "learning", lastReviewedAt = today + 1_000, repetitions = 1, intervalDays = 0.0),
            card("b", status = "review", lastReviewedAt = today - 86_400_000, repetitions = 4, intervalDays = 8.0),
        )
        val stats = LocalDashboard.build(cards, newLimit = 20, nowMs = today + 3_600_000)
        assertEquals(1, stats.reviews_done_today)
        assertEquals(1, stats.new_done_today)
        assertEquals(19, stats.new_remaining)
    }

    @Test
    fun forecastHasSevenDays() {
        val dueToday = card("t", status = "review", nextReviewAt = today + 1_000)
        val stats = LocalDashboard.build(listOf(dueToday), newLimit = 5, nowMs = today + 2_000)
        assertEquals(7, stats.forecast.size)
        assertEquals(1, stats.forecast[0].due_count)
        assertTrue(stats.forecast.drop(1).all { it.due_count == 0 })
    }

    private fun card(
        id: String,
        status: String,
        nextReviewAt: Long? = null,
        lastReviewedAt: Long? = null,
        intervalDays: Double = 0.0,
        repetitions: Int = 0,
        enrichment: String = "ready",
    ) = CachedCardEntity(
        id = id,
        profileId = "p",
        deckId = null,
        lemmaL2 = id,
        glossPrimary = id,
        pos = "noun",
        contentJson = "{}",
        enrichmentStatus = enrichment,
        status = status,
        nextReviewAt = nextReviewAt,
        lastReviewedAt = lastReviewedAt,
        intervalDays = intervalDays,
        repetitions = repetitions,
    )
}
