package com.vocabulario.app.ui.home

import com.vocabulario.app.data.local.LocalDashboard
import java.util.Calendar

/** Copy „następna powtórka”: jutro / pojutrze / dzień tygodnia / za N dni. */
object NextReviewCopy {
    enum class Kind { Tomorrow, DayAfter, Weekday, InDays }

    fun calendarDaysBetween(fromMs: Long, toMs: Long): Int {
        val a = LocalDashboard.startOfDayMs(fromMs)
        val b = LocalDashboard.startOfDayMs(toMs)
        var days = 0
        var cursor = a
        while (cursor < b && days < 400) {
            cursor = LocalDashboard.addDaysMs(cursor, 1)
            days++
        }
        return days
    }

    fun kind(days: Int, hasTomorrow: Boolean, hasDayAfter: Boolean): Kind = when {
        days == 1 && hasTomorrow -> Kind.Tomorrow
        days == 2 && hasDayAfter -> Kind.DayAfter
        days in 0..6 -> Kind.Weekday
        else -> Kind.InDays
    }

    fun weekdayCalendarConst(atMs: Long): Int {
        val cal = Calendar.getInstance()
        cal.timeInMillis = atMs
        return cal.get(Calendar.DAY_OF_WEEK)
    }
}
