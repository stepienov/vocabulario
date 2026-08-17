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
        val stats = LocalDashboard.build(cards, newLimit = 20, nowMs = now, newDoneToday = 0)
        assertEquals(1, stats.due_count)
        assertEquals(2, stats.srs_new)
        assertEquals(2, stats.new_reserve)
        assertEquals(2, stats.session_new)
        assertEquals(5, stats.cards_total)
        assertEquals(20, stats.new_limit)
        assertEquals(4, stats.ready_count)
    }

    @Test
    fun sessionNewRespectsDailyQuota() {
        val cards = (1..10).map { card("n$it", status = "new") }
        val stats = LocalDashboard.build(cards, newLimit = 20, nowMs = now, newDoneToday = 17)
        assertEquals(3, stats.session_new)
        assertEquals(3, stats.new_remaining)
        assertEquals(17, stats.new_done_today)
        assertEquals(10, stats.new_reserve)
    }

    @Test
    fun newOfferedNeverExceedsReserve() {
        assertEquals(4, LocalDashboard.newOffered(newLimit = 20, newDoneToday = 0, newReserve = 4))
        assertEquals(0, LocalDashboard.newOffered(newLimit = 20, newDoneToday = 20, newReserve = 40))
        assertEquals(5, LocalDashboard.newOffered(newLimit = 20, newDoneToday = 15, newReserve = 40))
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
        val stats = LocalDashboard.build(cards, newLimit = 20, nowMs = today + 3_600_000, newDoneToday = 0)
        assertEquals(1, stats.reviews_done_today)
        assertEquals(0, stats.new_done_today)
        assertEquals(20, stats.new_remaining)
    }

    @Test
    fun forecastIsFiveWeeksAndOverdueCountsToday() {
        val overdue = card("over", status = "review", nextReviewAt = today - 3 * 86_400_000L)
        val stats = LocalDashboard.build(listOf(overdue), newLimit = 5, nowMs = today + 2_000)
        assertEquals(35, stats.forecast.size)
        val todayCell = stats.forecast.first { it.start_ms == today }
        assertEquals(1, todayCell.due_count)
        assertTrue(stats.forecast.filter { it.start_ms != today }.all { it.due_count == 0 })
    }

    @Test
    fun nextReviewAfterNow() {
        val later = card("l", status = "review", nextReviewAt = now + 2 * 86_400_000L)
        val stats = LocalDashboard.build(listOf(later), newLimit = 5, nowMs = now)
        assertEquals(0, stats.due_count)
        assertTrue(stats.next_review_at != null)
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
