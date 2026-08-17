package com.vocabulario.app.ui.home

import org.junit.Assert.assertEquals
import org.junit.Test

class NextReviewCopyTest {

    @Test
    fun mondayScale() {
        assertEquals(NextReviewCopy.Kind.Tomorrow, NextReviewCopy.kind(1, true, true))
        assertEquals(NextReviewCopy.Kind.DayAfter, NextReviewCopy.kind(2, true, true))
        assertEquals(NextReviewCopy.Kind.Weekday, NextReviewCopy.kind(3, true, true))
        assertEquals(NextReviewCopy.Kind.Weekday, NextReviewCopy.kind(6, true, true))
        assertEquals(NextReviewCopy.Kind.InDays, NextReviewCopy.kind(7, true, true))
    }

    @Test
    fun englishSkipsDayAfter() {
        assertEquals(NextReviewCopy.Kind.Weekday, NextReviewCopy.kind(2, hasTomorrow = true, hasDayAfter = false))
    }
}
