package com.vocabulario.app.ui.settings

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ReminderTimeTest {
    @Test
    fun acceptsValidTimesIncludingMidnightAndEndOfDay() {
        assertEquals(0 to 0, parseReminderTime("00:00"))
        assertEquals(23 to 59, parseReminderTime("23:59"))
        assertEquals("09:05", formatReminderTime(9, 5))
    }

    @Test
    fun rejectsIncompleteAndOutOfRangeTimes() {
        listOf("", "19:0", "24:00", "12:60", "9:05", "ab:cd").forEach {
            assertNull(parseReminderTime(it))
        }
    }

    @Test
    fun formatsTypedAndPastedDigitsWithoutSavingIncompleteValues() {
        assertEquals("19", formatReminderInput("19"))
        assertEquals("19:0", formatReminderInput("190"))
        assertEquals("19:05", formatReminderInput("19:05"))
        assertEquals("19:05", formatReminderInput("190512"))
        assertNull(parseReminderTime(formatReminderInput("190")))
    }
}
