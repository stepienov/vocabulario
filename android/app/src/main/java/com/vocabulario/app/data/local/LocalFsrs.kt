package com.vocabulario.app.data.local

import com.vocabulario.app.data.local.db.CachedCardEntity
import io.github.openspacedrepetition.Card
import io.github.openspacedrepetition.Rating
import io.github.openspacedrepetition.Scheduler
import io.github.openspacedrepetition.State
import java.time.Duration
import java.time.Instant
import kotlin.math.max
import kotlin.math.min

/**
 * Oficjalne FSRS na urządzeniu (java-fsrs), z parametrami jak py-fsrs 6.3.x na backendzie.
 * Mapowanie: stability, difficulty, due→nextReviewAt, step→fsrsStep, state→status, last_review.
 */
object LocalFsrs {

    /** Domyślne wagi py-fsrs 6.3.1 (backend `Scheduler()`). */
    private val PARAMETERS = doubleArrayOf(
        0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001, 1.8722, 0.1666, 0.796,
        1.4835, 0.0614, 0.2629, 1.6483, 0.6014, 1.8729, 0.5425, 0.0912, 0.0658, 0.1542,
    )

    private val scheduler: Scheduler = Scheduler.builder()
        .parameters(PARAMETERS)
        .desiredRetention(0.9)
        .learningSteps(arrayOf(Duration.ofMinutes(1), Duration.ofMinutes(10)))
        .relearningSteps(arrayOf(Duration.ofMinutes(10)))
        .maximumInterval(36500)
        .enableFuzzing(true)
        .build()

    fun apply(
        card: CachedCardEntity,
        grade: String,
        correct: Boolean,
        nowMs: Long = System.currentTimeMillis(),
    ): CachedCardEntity {
        val g = normalizeGrade(if (!correct) "again" else grade)
        val rating = toRating(g)
        val now = Instant.ofEpochMilli(nowMs)
        val fsrsCard = toFsrsCard(card, now)
        val updated = try {
            scheduler.reviewCard(fsrsCard, rating, now).card()
        } catch (_: Exception) {
            val fresh = Card.builder()
                .cardId(stableCardId(card.id))
                .due(now)
                .build()
            scheduler.reviewCard(fresh, rating, now).card()
        }
        return fromFsrsCard(card, updated, g, nowMs, rating == Rating.AGAIN)
    }

    private fun normalizeGrade(grade: String): String =
        when (grade.lowercase()) {
            "know_well" -> "easy"
            else -> grade.lowercase()
        }

    private fun toRating(grade: String): Rating =
        when (grade) {
            "again" -> Rating.AGAIN
            "hard" -> Rating.HARD
            "easy" -> Rating.EASY
            else -> Rating.GOOD
        }

    private fun toFsrsCard(card: CachedCardEntity, now: Instant): Card {
        if (card.status == "new" || (card.stability == null && card.status !in legacyStatuses)) {
            return Card.builder()
                .cardId(stableCardId(card.id))
                .due(now)
                .build()
        }

        // Legacy SM-2 → FSRS (jak backend `_seed_from_legacy`)
        if (card.stability == null && card.status in legacyStatuses && card.intervalDays > 0) {
            return seedFromLegacy(card, now)
        }

        val state = statusToState(card.status)
        val step = if (state == State.REVIEW) null else (card.fsrsStep ?: 0)
        val builder = Card.builder()
            .cardId(stableCardId(card.id))
            .state(state)
            .step(step)
            .stability(card.stability)
            .difficulty(card.difficulty ?: 5.0)
            .due(card.nextReviewAt?.let(Instant::ofEpochMilli) ?: now)
        card.lastReviewedAt?.let { builder.lastReview(Instant.ofEpochMilli(it)) }
        return builder.build()
    }

    private fun seedFromLegacy(card: CachedCardEntity, now: Instant): Card {
        if (card.nextReviewAt == null) {
            return Card.builder().cardId(stableCardId(card.id)).due(now).build()
        }
        val interval = max(card.intervalDays, 0.1)
        val ease = card.ease
        val difficulty = max(1.0, min(10.0, 11.0 - ease * 2.5))
        val state = if (card.status == "review") State.REVIEW else State.LEARNING
        val lastReview = card.lastReviewedAt?.let(Instant::ofEpochMilli)
            ?: Instant.ofEpochMilli(card.nextReviewAt).minus(Duration.ofMillis((interval * 86_400_000).toLong()))
        return Card.builder()
            .cardId(stableCardId(card.id))
            .state(state)
            .step(if (state == State.REVIEW) null else 0)
            .stability(interval)
            .difficulty(difficulty)
            .due(Instant.ofEpochMilli(card.nextReviewAt))
            .lastReview(lastReview)
            .build()
    }

    private fun fromFsrsCard(
        original: CachedCardEntity,
        updated: Card,
        grade: String,
        nowMs: Long,
        wasAgain: Boolean,
    ): CachedCardEntity {
        val lastReview = updated.lastReview ?: Instant.ofEpochMilli(nowMs)
        val due = updated.due
        val intervalDays = max(
            0.0,
            Duration.between(lastReview, due).toMillis().toDouble() / 86_400_000.0,
        )
        val difficulty = updated.difficulty
        val ease = if (difficulty != null) {
            max(1.3, min(3.0, (11.0 - difficulty) / 2.5))
        } else {
            original.ease
        }
        return original.copy(
            status = stateToStatus(updated.state),
            nextReviewAt = due.toEpochMilli(),
            lastReviewedAt = lastReview.toEpochMilli(),
            intervalDays = intervalDays,
            ease = ease,
            repetitions = original.repetitions + 1,
            lapses = original.lapses + if (wasAgain) 1 else 0,
            stability = updated.stability,
            difficulty = difficulty,
            fsrsStep = updated.step,
            lastGrade = grade,
            updatedAt = nowMs,
        )
    }

    private fun statusToState(status: String): State =
        when (status) {
            "review" -> State.REVIEW
            "relearning" -> State.RELEARNING
            else -> State.LEARNING
        }

    private fun stateToStatus(state: State): String =
        when (state) {
            State.REVIEW -> "review"
            State.RELEARNING -> "relearning"
            else -> "learning"
        }

    private fun stableCardId(id: String): Int {
        val h = id.hashCode()
        return if (h == Int.MIN_VALUE) 0 else kotlin.math.abs(h)
    }

    private val legacyStatuses = setOf("learning", "review", "relearning")
}
