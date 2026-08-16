package com.vocabulario.app.data.local

import com.vocabulario.app.data.api.DashboardForecastDay
import com.vocabulario.app.data.api.DashboardStatsResponse
import com.vocabulario.app.data.local.db.CachedCardEntity
import java.util.Calendar

/**
 * Dashboard z kart w Room — bez GET /stats. Liczby mają być zgodne z lokalną kolejką SRS.
 */
object LocalDashboard {
    const val MASTERED_INTERVAL_DAYS = 21.0

    fun build(
        learningCards: List<CachedCardEntity>,
        newLimit: Int,
        nowMs: Long,
        periodDays: Int = 7,
    ): DashboardStatsResponse {
        val ready = learningCards.filter { it.enrichmentStatus == "ready" }
        val due = ready.filter { isDue(it, nowMs) }
        val newCards = ready.filter { it.status == "new" }
        val learning = learningCards.count { it.status == "learning" }
        val shortReview = learningCards.count {
            it.status == "review" && it.intervalDays < MASTERED_INTERVAL_DAYS
        }
        val mastered = learningCards.count {
            it.status == "review" && it.intervalDays >= MASTERED_INTERVAL_DAYS
        }
        val todayStart = startOfDayMs(nowMs)
        val reviewedToday = learningCards.filter { card ->
            val at = card.lastReviewedAt ?: return@filter false
            at >= todayStart
        }
        val newDoneToday = reviewedToday.count { it.repetitions == 1 || it.intervalDays < 1.0 }
        val reviewsDoneToday = reviewedToday.size
        val newRemaining = (newLimit - newDoneToday).coerceAtLeast(0)
        val lastReviewed = learningCards.maxOfOrNull { it.lastReviewedAt ?: 0L }
            ?.takeIf { it > 0L }
            ?.let { java.time.Instant.ofEpochMilli(it).toString() }
        val lastAdded = learningCards.maxOfOrNull { it.updatedAt }
            ?.takeIf { it > 0L }
            ?.let { java.time.Instant.ofEpochMilli(it).toString() }

        return DashboardStatsResponse(
            due_count = due.size,
            new_remaining = newRemaining,
            new_done_today = newDoneToday,
            new_limit = newLimit,
            reviews_done_today = reviewsDoneToday,
            done_today = reviewsDoneToday,
            srs_new = newCards.size,
            srs_due = due.size,
            srs_learning = learning + shortReview,
            srs_mastered = mastered,
            new_reserve = newCards.size,
            cards_total = learningCards.size,
            forecast = forecast(ready, nowMs),
            last_added_at = lastAdded,
            last_reviewed_at = lastReviewed,
            new_today = newDoneToday,
            reviews_in_period = reviewsDoneToday,
            avg_words_per_day = newDoneToday.toDouble(),
            period_days = periodDays,
        )
    }

    fun isDue(card: CachedCardEntity, nowMs: Long): Boolean {
        if (card.status == "new" || card.status.isBlank()) return false
        val next = card.nextReviewAt ?: return true
        return next <= nowMs
    }

    fun startOfDayMs(nowMs: Long): Long {
        val cal = Calendar.getInstance()
        cal.timeInMillis = nowMs
        cal.set(Calendar.HOUR_OF_DAY, 0)
        cal.set(Calendar.MINUTE, 0)
        cal.set(Calendar.SECOND, 0)
        cal.set(Calendar.MILLISECOND, 0)
        return cal.timeInMillis
    }

    private fun forecast(ready: List<CachedCardEntity>, nowMs: Long): List<DashboardForecastDay> {
        val todayStart = startOfDayMs(nowMs)
        val dayMs = 86_400_000L
        return (0 until 7).map { offset ->
            val start = todayStart + offset * dayMs
            val end = start + dayMs
            val count = ready.count { card ->
                if (card.status !in DUE_STATUSES) return@count false
                val next = card.nextReviewAt ?: return@count offset == 0
                next in start until end
            }
            DashboardForecastDay(day_offset = offset, label = "", due_count = count)
        }
    }

    private val DUE_STATUSES = setOf("learning", "review", "relearning")
}
