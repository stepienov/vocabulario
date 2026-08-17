package com.vocabulario.app.data.local

import com.vocabulario.app.data.local.db.CachedCardEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LocalFsrsTest {

    private val now = 1_700_000_000_000L

    @Test
    fun gradesNewCardForEachRating() {
        for (grade in listOf("again", "hard", "good", "easy")) {
            val updated = LocalFsrs.apply(newCard(), grade, correct = true, nowMs = now)
            assertNotNull(updated.nextReviewAt)
            assertTrue(updated.status != "new")
            assertEquals(grade, updated.lastGrade)
        }
    }

    @Test
    fun againOnWrongAnswerStoresAgain() {
        val updated = LocalFsrs.apply(newCard(), "easy", correct = false, nowMs = now)
        assertEquals("again", updated.lastGrade)
        assertEquals(1, updated.lapses)
    }

    @Test
    fun reviewsExistingLearningCard() {
        val learning = newCard().copy(
            status = "learning",
            stability = 0.4,
            difficulty = 5.0,
            fsrsStep = 0,
            nextReviewAt = now,
            lastReviewedAt = now - 60_000,
        )
        val updated = LocalFsrs.apply(learning, "good", correct = true, nowMs = now)
        assertNotNull(updated.nextReviewAt)
        assertTrue(updated.repetitions == 1)
    }

    private fun newCard() = CachedCardEntity(
        id = "card-1",
        profileId = "p",
        lemmaL2 = "hola",
        glossPrimary = "cześć",
        pos = "interjection",
        contentJson = "{}",
        status = "new",
        nextReviewAt = null,
    )
}
