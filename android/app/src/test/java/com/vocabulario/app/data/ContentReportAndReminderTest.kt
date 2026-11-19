package com.vocabulario.app.data

import com.vocabulario.app.data.api.ReportLimits
import com.vocabulario.app.notifications.NotificationScheduler
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Calendar

class ContentReportAndReminderTest {

    @Test
    fun permanentRejectionCoversClientErrorsExceptRetryableOnes() {
        listOf(400, 404, 409, 422).forEach { assertTrue("$it", isPermanentRejection(it)) }
        listOf(401, 403, 408, 429, 500, 503).forEach { assertFalse("$it", isPermanentRejection(it)) }
    }

    @Test
    fun requestTrimsAndCapsTextAndDropsBlankNote() {
        val draft = ContentReportDraft(
            profileId = "p1",
            targetKind = "card",
            targetId = "c1",
            field = "other",
            reason = "incorrect",
            excerpt = "  " + "x".repeat(ReportLimits.EXCERPT_MAX + 50),
            note = "   ",
        )
        val request = requestFor(draft, "r1")
        assertEquals("r1", request.client_report_id)
        assertEquals(ReportLimits.EXCERPT_MAX, request.excerpt.length)
        assertNull(request.note)
        val noted = requestFor(draft.copy(note = "n".repeat(ReportLimits.NOTE_MAX + 5)), "r2")
        assertEquals(ReportLimits.NOTE_MAX, noted.note?.length)
    }

    @Test
    fun reminderShowsOncePerDayForBoundOwnerOnly() {
        val now = Calendar.getInstance().apply { set(2026, Calendar.MARCH, 10) }
        val today = NotificationScheduler.reminderDayKey("u1", now)
        assertTrue(NotificationScheduler.shouldShowReminder(true, "u1", "u1", null, today))
        assertFalse(NotificationScheduler.shouldShowReminder(true, "u1", "u1", today, today))
        assertFalse(NotificationScheduler.shouldShowReminder(true, "u1", "u2", null, today))
        assertFalse(NotificationScheduler.shouldShowReminder(true, "u1", null, null, today))
        assertFalse(NotificationScheduler.shouldShowReminder(false, "u1", "u1", null, today))
        val tomorrow = NotificationScheduler.reminderDayKey("u1", (now.clone() as Calendar).apply { add(Calendar.DAY_OF_YEAR, 1) })
        assertTrue(NotificationScheduler.shouldShowReminder(true, "u1", "u1", today, tomorrow))
    }
}
