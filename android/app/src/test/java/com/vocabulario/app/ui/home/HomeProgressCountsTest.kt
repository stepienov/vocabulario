package com.vocabulario.app.ui.home

import com.vocabulario.app.data.api.DashboardStatsResponse
import org.junit.Assert.assertEquals
import org.junit.Test

class HomeProgressCountsTest {

    @Test
    fun alreadyKnowAndRemainingUseMasteredAndTotal() {
        val state = HomeUiState(
            stats = DashboardStatsResponse(
                srs_mastered = 12,
                srs_learning = 30,
                srs_new = 8,
                cards_total = 50,
                ready_count = 40,
            ),
        )
        assertEquals(12, state.alreadyKnowCount)
        assertEquals(50, state.currentlyLearningCount)
        assertEquals(38, state.remainingToLearnCount)
    }

    @Test
    fun remainingNeverGoesNegative() {
        val state = HomeUiState(
            stats = DashboardStatsResponse(
                srs_mastered = 5,
                cards_total = 3,
                ready_count = 3,
            ),
        )
        assertEquals(0, state.remainingToLearnCount)
    }

    @Test
    fun missingStatsAreZero() {
        val state = HomeUiState()
        assertEquals(0, state.alreadyKnowCount)
        assertEquals(0, state.currentlyLearningCount)
        assertEquals(0, state.remainingToLearnCount)
    }
}
