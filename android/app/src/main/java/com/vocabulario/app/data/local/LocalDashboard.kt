package com.vocabulario.app.data.local

import com.vocabulario.app.data.api.DashboardForecastDay
import com.vocabulario.app.data.api.DashboardStatsResponse
import com.vocabulario.app.data.local.db.CachedCardEntity
import java.time.Instant
import java.util.Calendar

/**
 * Dashboard z kart w Room — bez GET /stats. Liczby mają być zgodne z lokalną kolejką SRS.
 */
object LocalDashboard {
    const val MASTERED_INTERVAL_DAYS = 21.0
    const val FORECAST_CELLS = 35

    fun build(
        learningCards: List<CachedCardEntity>,
        newLimit: Int,
        nowMs: Long,
        periodDays: Int = 7,
        newDoneToday: Int = 0,
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
        val doneToday = newDoneToday.coerceAtLeast(0)
        val newRemaining = if (newLimit > 0) (newLimit - doneToday).coerceAtLeast(0) else newCards.size
        val sessionNew = if (newLimit > 0) minOf(newRemaining, newCards.size) else newCards.size
        val reviewsDoneToday = reviewedToday.size
        val lastReviewed = learningCards.maxOfOrNull { it.lastReviewedAt ?: 0L }
            ?.takeIf { it > 0L }
            ?.let { Instant.ofEpochMilli(it).toString() }
        val lastAdded = learningCards.maxOfOrNull { it.updatedAt }
            ?.takeIf { it > 0L }
            ?.let { Instant.ofEpochMilli(it).toString() }
        val nextReview = nextReviewAtMs(ready, nowMs)?.let { Instant.ofEpochMilli(it).toString() }

        return DashboardStatsResponse(
            due_count = due.size,
            new_remaining = newRemaining,
            new_done_today = doneToday,
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
            new_today = doneToday,
            reviews_in_period = reviewsDoneToday,
            avg_words_per_day = doneToday.toDouble(),
            period_days = periodDays,
            ready_count = ready.size,
            session_new = sessionNew,
            next_review_at = nextReview,
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

    fun startOfWeekMondayMs(nowMs: Long): Long {
        val cal = Calendar.getInstance()
        cal.timeInMillis = startOfDayMs(nowMs)
        val daysFromMonday = (cal.get(Calendar.DAY_OF_WEEK) + 5) % 7
        cal.add(Calendar.DAY_OF_MONTH, -daysFromMonday)
        return cal.timeInMillis
    }

    fun addDaysMs(startMs: Long, days: Int): Long {
        val cal = Calendar.getInstance()
        cal.timeInMillis = startMs
        cal.add(Calendar.DAY_OF_MONTH, days)
        return cal.timeInMillis
    }

    fun newOffered(newLimit: Int, newDoneToday: Int, newReserve: Int): Int {
        if (newLimit <= 0) return newReserve
        return minOf((newLimit - newDoneToday).coerceAtLeast(0), newReserve)
    }

    fun nextReviewAtMs(ready: List<CachedCardEntity>, nowMs: Long): Long? =
        ready.asSequence()
            .filter { it.status in DUE_STATUSES }
            .mapNotNull { it.nextReviewAt }
            .filter { it > nowMs }
            .minOrNull()

    private fun forecast(ready: List<CachedCardEntity>, nowMs: Long): List<DashboardForecastDay> {
        val weekStart = startOfWeekMondayMs(nowMs)
        val todayStart = startOfDayMs(nowMs)
        val todayEnd = addDaysMs(todayStart, 1)
        return (0 until FORECAST_CELLS).map { offset ->
            val start = addDaysMs(weekStart, offset)
            val end = addDaysMs(start, 1)
            val isToday = start == todayStart
            val count = ready.count { card ->
                if (card.status !in DUE_STATUSES) return@count false
                val next = card.nextReviewAt ?: return@count isToday
                if (isToday) next < todayEnd else next in start until end
            }
            DashboardForecastDay(
                day_offset = offset,
                label = "",
                due_count = count,
                start_ms = start,
            )
        }
    }

    private val DUE_STATUSES = setOf("learning", "review", "relearning")
}
