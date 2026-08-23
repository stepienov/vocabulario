package com.vocabulario.app.ui.home

import com.vocabulario.app.data.local.LocalDashboard
import org.junit.Assert.assertEquals
import org.junit.Test

class NextReviewCopyTest {

    @Test
    fun calendarDayBoundaries() {
        val start = LocalDashboard.startOfDayMs(1_700_000_000_000L)
        assertEquals(1, NextReviewCopy.calendarDaysBetween(start, LocalDashboard.addDaysMs(start, 1)))
        assertEquals(2, NextReviewCopy.calendarDaysBetween(start, LocalDashboard.addDaysMs(start, 2)))
        assertEquals(7, NextReviewCopy.calendarDaysBetween(start, LocalDashboard.addDaysMs(start, 7)))
    }

    @Test
    fun classifyTomorrowAndDayAfter() {
        val start = LocalDashboard.startOfDayMs(1_700_000_000_000L)
        assertEquals(
            NextReviewCopy.Kind.Tomorrow,
            NextReviewCopy.classify(start, LocalDashboard.addDaysMs(start, 1)).kind,
        )
        assertEquals(
            NextReviewCopy.Kind.DayAfter,
            NextReviewCopy.classify(start, LocalDashboard.addDaysMs(start, 2)).kind,
        )
    }
}
